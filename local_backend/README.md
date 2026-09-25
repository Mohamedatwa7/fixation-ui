# F1X8 local backend (plan B for Modal)

Runs the full diagnostic pipeline on this machine's RTX 5090 instead of the
Modal workspace (`fixation-api`), which is offline pending account review.
The Next.js frontend works unchanged — point `NEXT_PUBLIC_API_URL` here.

## Layout

- `app.py` — FastAPI server mirroring `modal_app.py`'s endpoints
  (`/api/analyze/image[/submit]`, `/api/analyze/video/submit`,
  `/api/analyze/video-url/submit`, `/api/job/{id}`, `/health`).
  It imports `../modal_app.py` with a stubbed `modal` module, so all scoring,
  judge-ensemble, and prompt logic stays single-sourced there — do not copy
  scoring changes here, make them in `modal_app.py`.
- `shims/` — local reimplementations of `extract_keyframes.py` and
  `analyze_audio.py`, whose originals exist **only on the Modal volume**.
  Replace with the originals once the volume is reachable
  (`modal volume get fixation-assets ...`).
- `weights/TASED_updated.pt` — public TASED-Net checkpoint (video gaze saliency).
- `benchmarks/` — EMPTY until recovered from the Modal volume. Without them
  image KPIs simply omit MAdVerse percentiles (frontend falls back to 50th).
- `hf-cache/` — Qwen2.5-VL-7B + Whisper downloads (~17 GB on first run).
- `D:\content\TASED-Net` — repo clone; `saliency_module.py` hardcodes
  `/content/TASED-Net`, which resolves there when the server runs from D:.

## Setup / run

```powershell
.\setup.ps1     # once: venv, CUDA torch, deps, TASED repo + weights
.\run.ps1       # serves on http://0.0.0.0:8010
```

Port 8010 because another local model server already occupies 8000.
Requires `ffmpeg` on PATH (installed via winget) and `ANTHROPIC_API_KEY`
(read automatically from `..\.env`).

## Pointing the frontend at it

- Local dev: set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010` in `.env.local`.
- Deployed Vercel frontend: expose the server publicly first, e.g.
  `cloudflared tunnel --url http://localhost:8010`, then set the Vercel env
  `NEXT_PUBLIC_API_URL` to the printed `*.trycloudflare.com` URL and redeploy.

## Known degradations vs. Modal

- No MAdVerse percentiles until `benchmarks/*.json` are recovered.
- Organic score uses the weight-based formula; the fine-tuned ranker
  (`fixation-ranker-api`) lives on Modal and is unreachable (`_rank_score`
  falls back automatically).
- `shims/` keyframe + audio modules are interface-faithful rewrites, not the
  original code — timelines/scores are comparable but not bit-identical.
- One GPU: concurrent jobs are serialized by a lock (they queue as
  "analyzing" rather than wedging like on Modal).
