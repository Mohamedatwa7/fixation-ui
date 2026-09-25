"""Local Windows backend for F1X8 — plan B while the Modal workspace is offline.

Mirrors the HTTP surface of modal_app.py (image/video submit + poll endpoints)
so the Next.js frontend works unchanged with NEXT_PUBLIC_API_URL pointed here.
The scoring/judge logic is NOT duplicated: modal_app.py is imported with a
stubbed `modal` module and its module-level functions are reused directly.
Only the serving layer (job store, paths, subprocess wiring) is local.

Run with run.ps1 (or: .venv\\Scripts\\python -m uvicorn app:app --port 8000).
"""

import os
import sys
import json
import base64
import subprocess
import uuid
import threading
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # D:\F1X8\local_backend
REPO = ROOT.parent                                # D:\F1X8
SCRIPTS_DIR = REPO / "backend_scripts"
SHIMS_DIR = ROOT / "shims"                        # local extract_keyframes / analyze_audio
TASED_REPO = Path(r"D:\content\TASED-Net")        # saliency_module hardcodes /content/TASED-Net
TASED_WEIGHTS = ROOT / "weights" / "TASED_updated.pt"
MODEL_CACHE = ROOT / "hf-cache"
BENCH_DIR = ROOT / "benchmarks"                   # drop volume benchmark JSONs here when recovered
TMP = ROOT / "tmp"

for _d in (MODEL_CACHE, TMP, ROOT / "weights", BENCH_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_env():
    """Read ANTHROPIC_API_KEY etc. from the repo .env without clobbering the shell."""
    env_file = REPO / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()
os.environ.setdefault("HF_HOME", str(MODEL_CACHE))
# fetch_video shells out to the yt-dlp binary; make sure the venv Scripts dir wins.
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")


# ── Stub `modal` so modal_app.py imports cleanly without a Modal account ────
class _Anything:
    """Absorbs any attribute access / call chain (Image.debian_slim()... etc.)."""

    def __call__(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        return self


_modal_stub = types.ModuleType("modal")
for _name in ("Image", "Volume", "Dict", "App", "Secret", "asgi_app"):
    setattr(_modal_stub, _name, _Anything())
sys.modules["modal"] = _modal_stub

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO))
import modal_app as core  # noqa: E402  (scoring, judge ensemble, prompts)

JOBS: dict = {}                    # replaces modal.Dict — one process, plain dict
_GPU_LOCK = threading.Lock()       # one GPU: serialize analyses instead of wedging


def benchmark_for(format_type):
    """Local benchmark file if recovered from the Modal volume, else None
    (image_kpis handles a missing benchmark by omitting percentiles)."""
    key = core._FORMAT_BENCHMARK.get((format_type or "").strip().lower(), "online")
    local = BENCH_DIR / Path(core.BENCHMARKS[key]).name
    return str(local) if local.exists() else None


def b64(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Image pipeline (in-process, same as Modal did) ──────────────────────────

def _image_result(image_path, title, description, format_type, role, lite=False):
    from analyze_image import analyze_image

    judgment = core.assess_engagement(
        [(core._media_type(image_path), b64(image_path))],
        context_text=core._context_text(title, description, format_type))
    report = analyze_image(
        image_path=image_path,
        title=title or None,
        description=description or None,
        format_type=format_type,
        output_path=str(TMP / f"image_report_{uuid.uuid4().hex[:8]}.json"),
        model_cache=str(MODEL_CACHE),
        benchmark_path=benchmark_for(format_type),
        role_key=role,
        lite=lite,
        funnel_hint=judgment.get("funnel_stage"),
        score_weights={"funnel": core._FUNNEL_WEIGHTS["image"], "organic": core._ORGANIC_WEIGHTS},
    )
    overlay = report.get("saliency", {}).get("overlay_path")
    kpi_data = report.get("kpis", {})
    measured = kpi_data.get("kpis", {})
    funnel = judgment.get("funnel_stage") or kpi_data.get("funnel_stage") or "mid"
    engagement_potential, five_kpis, organic = core.aggregate_engagement(
        measured, judgment, "image", funnel)
    rank = core._rank_score(image_path)
    ctx_fit = (core._assess_context_fit(
        [(core._media_type(image_path), b64(image_path))],
        core._context_text(title, description, format_type),
        engagement_potential) if description else None)
    return {
        **(ctx_fit or {}),
        "verdict": report.get("diagnosis", {}),
        "engagement_potential": engagement_potential,
        "score": engagement_potential,
        "organic_engagement": rank if rank is not None else organic,
        "organic_source": "ranker" if rank is not None else "weights",
        "organic_weights_score": organic,
        "kpis": five_kpis,
        "kpis_overall": engagement_potential,
        "funnel_stage": funnel,
        "product_tier": judgment.get("product_tier") or kpi_data.get("product_tier"),
        "localization": report.get("localization"),
        "heatmap": b64(overlay),
        "heatmap_type": "image/png",
    }


def _run_image(job_id, image_path, title, description, format_type, role):
    try:
        JOBS[job_id] = {"status": "analyzing"}
        with _GPU_LOCK:
            result = _image_result(image_path, title, description, format_type, role)
        JOBS[job_id] = {"status": "done", "result": result}
    except Exception as e:
        import traceback
        JOBS[job_id] = {"status": "error", "error": str(e),
                        "trace": traceback.format_exc()[-800:]}
    finally:
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass


# ── Video pipeline (subprocess, same as Modal did) ──────────────────────────

def _run_video(job_id, video_path, title=None, description=None):
    try:
        print(f"[build] local-backend job={job_id}")
        JOBS[job_id] = {"status": "analyzing"}
        out = str(TMP / f"video_{job_id}.json")
        cmd = [
            sys.executable, str(SCRIPTS_DIR / "diagnose_video_v5.py"),
            "--video-path", video_path,
            "--output", out,
            "--model-cache", str(MODEL_CACHE),
            "--tased-weights", str(TASED_WEIGHTS),
        ]
        if title:
            cmd += ["--title", title]
        if description:
            cmd += ["--description", " ".join(description.split())[:800]]
        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"
        # os.pathsep (";" on Windows) — modal_app hardcoded ":" and would break here.
        env["PYTHONPATH"] = os.pathsep.join([str(SCRIPTS_DIR), str(SHIMS_DIR), str(TASED_REPO)])
        env["FORCE_QWENVL_VIDEO_READER"] = "decord"
        env["HF_HOME"] = str(MODEL_CACHE)
        env["PYTHONIOENCODING"] = "utf-8"
        with _GPU_LOCK:
            # cwd on D: so the scripts' hardcoded /content, /tmp paths resolve on D:\.
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                               env=env, cwd=str(ROOT), encoding="utf-8", errors="replace")
        if r.returncode != 0 or not os.path.exists(out):
            JOBS[job_id] = {"status": "error", "error": (r.stderr or "no output")[-1200:]}
            return
        with open(out, encoding="utf-8") as f:
            report = json.load(f)

        bad = {k: v for k, v in (report.get("perception") or {}).items()
               if isinstance(v, str) and v.startswith("[error")}
        if bad:
            print(f"perception errors ({len(bad)}/{len(report.get('perception') or {})}): "
                  f"{json.dumps(bad)[:1500]}")

        kpis_block = {}
        try:
            from cognitive_kpis import compute_cognitive_kpis
            kpi_data = compute_cognitive_kpis(report)
            kpis_block = kpi_data.get("kpis", {})
        except Exception as ke:
            print(f"KPI computation failed: {ke}")

        sal = report.get("saliency", {}).get("overlay_video")
        sal_web = None
        if sal and os.path.exists(sal):
            sal_web = sal + "_web.mp4"
            tx = subprocess.run(
                ["ffmpeg", "-y", "-i", sal, "-vf", "scale=-2:480",
                 "-c:v", "libx264", "-crf", "32", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", sal_web],
                capture_output=True, text=True,
            )
            if tx.returncode != 0 or not os.path.exists(sal_web):
                print(f"ffmpeg transcode failed: {tx.stderr[-400:]}")
                sal_web = sal

        frames = core._sample_frames(video_path, 3)
        judgment = core.assess_engagement(
            frames, context_text=core._context_text(title, description))
        funnel = judgment.get("funnel_stage") or "mid"
        engagement_potential, five_kpis, organic = core.aggregate_engagement(
            kpis_block, judgment, "video", funnel)
        heatmap_b64 = b64(sal_web)
        ctx_fit = (core._assess_context_fit(frames, core._context_text(title, description),
                                            engagement_potential)
                   if description and frames else None)
        JOBS[job_id] = {
            "status": "done",
            "result": {
                **(ctx_fit or {}),
                "verdict": report.get("diagnosis", {}),
                "engagement_potential": engagement_potential,
                "score": engagement_potential,
                "organic_engagement": organic,
                "kpis": five_kpis,
                "kpis_overall": engagement_potential,
                "benchmarkPercentile": core._cohort_percentile(organic),
                "funnel_stage": funnel,
                "product_tier": judgment.get("product_tier"),
                "heatmap": heatmap_b64,
                "heatmap_type": "video/mp4",
                "timelines": {
                    "attention": report.get("key_frames", {}).get("metadata", {}).get("score_timeline", []),
                    "audio_energy": report.get("audio", {}).get("signals", {}).get("energy_timeline", []),
                },
            },
        }
    except Exception as e:
        JOBS[job_id] = {"status": "error", "error": str(e)}
    finally:
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass


# ── FastAPI app ──────────────────────────────────────────────────────────────

from fastapi import FastAPI, File, UploadFile, Form  # noqa: E402

app = FastAPI(title="F1X8 local backend")


@app.post("/api/analyze/image")
async def analyze_image_endpoint(
    file: UploadFile = File(...),
    title: str = Form(None), description: str = Form(None),
    format_type: str = Form("KV"), role: str = Form("creative_director"),
    lite: str = Form(None),
):
    tmp = str(TMP / f"upload_{uuid.uuid4().hex[:8]}_{file.filename}")
    with open(tmp, "wb") as f:
        f.write(await file.read())
    try:
        with _GPU_LOCK:
            return _image_result(tmp, title, description, format_type, role, lite=bool(lite))
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()[-800:]}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


@app.post("/api/analyze/image/submit")
async def submit_image(
    file: UploadFile = File(...),
    title: str = Form(None), description: str = Form(None),
    format_type: str = Form("KV"), role: str = Form("creative_director"),
):
    job_id = str(uuid.uuid4())
    tmp = str(TMP / f"upload_{job_id}_{file.filename}")
    with open(tmp, "wb") as f:
        f.write(await file.read())
    JOBS[job_id] = {"status": "analyzing"}
    threading.Thread(target=_run_image,
                     args=(job_id, tmp, title, description, format_type, role),
                     daemon=True).start()
    return {"job_id": job_id}


@app.post("/api/analyze/video/submit")
async def submit_video_file(file: UploadFile = File(...), role: str = Form("creative_director"),
                            title: str = Form(None), description: str = Form(None)):
    job_id = str(uuid.uuid4())
    tmp = str(TMP / f"upload_{job_id}_{file.filename}")
    with open(tmp, "wb") as f:
        f.write(await file.read())
    JOBS[job_id] = {"status": "analyzing"}
    threading.Thread(target=_run_video, args=(job_id, tmp, title, description),
                     daemon=True).start()
    return {"job_id": job_id}


@app.post("/api/analyze/video-url/submit")
async def submit_video_url(url: str = Form(...), role: str = Form("creative_director"),
                           title: str = Form(None), description: str = Form(None)):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "fetching"}

    def work():
        try:
            import fetch_video
            fetched = fetch_video.fetch_video(url, output_dir=str(TMP / "fetched"))
            if "error" in fetched:
                JOBS[job_id] = {"status": "error", "error": fetched.get("error")}
                return
            _run_video(job_id, fetched["video_path"], title, description)
        except Exception as e:
            JOBS[job_id] = {"status": "error", "error": str(e)}

    threading.Thread(target=work, daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/job/{job_id}")
async def job_status(job_id: str):
    return JOBS.get(job_id, {"status": "not_found"})


@app.get("/health")
async def health():
    info = {"status": "ok", "backend": "local",
            "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "tased_weights": TASED_WEIGHTS.exists(),
            "benchmarks": sorted(p.name for p in BENCH_DIR.glob("*.json"))}
    try:
        import torch
        info["cuda"] = torch.cuda.is_available()
        if info["cuda"]:
            info["gpu"] = torch.cuda.get_device_name(0)
    except Exception as e:
        info["cuda"] = f"torch unavailable: {e}"
    return info
