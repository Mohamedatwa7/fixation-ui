"""TRIBE v2 feature extraction over the F1X8 calibration set (research use).

Runs Meta's TRIBE v2 brain-response encoder (CC BY-NC — research context only)
on each calibration creative and reduces the predicted cortical response
(n_timesteps x ~20k fsaverage5 vertices) to per-network summary features via
the Schaefer-400 / Yeo-7 surface parcellation.

Usage:
  python eval/tribe/build_manifest.py
  modal run eval/tribe/modal_tribe.py --smoke true          # 2 images + 1 reel
  modal run eval/tribe/modal_tribe.py                       # full set
  modal run eval/tribe/modal_tribe.py --only-kind image
Results merge into eval/tribe/features.json (resumable: done ids are skipped).
"""
import base64
import json
import os

import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install("torch", "torchvision", "torchaudio")
    .pip_install(
        "git+https://github.com/facebookresearch/tribev2.git",
        "nibabel", "pandas", "huggingface_hub", "yt-dlp", "curl-cffi",
    )
    # tribev2 pins torch 2.6.0+cu124 but lets torchaudio float to a CUDA-13
    # build that can't load (libcudart.so.13). Pin it to the matching version.
    .pip_install("torchaudio==2.6.0")
)
cache = modal.Volume.from_name("tribe-cache", create_if_missing=True)
app = modal.App("tribe-features", image=image)

# Schaefer 2018, 400 parcels, Yeo 7-network ordering, on the fsaverage5 surface.
_CBIG = ("https://raw.githubusercontent.com/ThomasYeoLab/CBIG/master/stable_projects/"
         "brain_parcellation/Schaefer2018_LocalGlobal/Parcellations/FreeSurfer5.3/"
         "fsaverage5/label/{h}.Schaefer2018_400Parcels_7Networks_order.annot")
NETWORKS = ["Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default"]

_secrets = []
if os.environ.get("HF_TOKEN"):
    _secrets.append(modal.Secret.from_dict({"HF_TOKEN": os.environ["HF_TOKEN"]}))


def _run(cmd, **kw):
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {(r.stderr or r.stdout)[-400:]}")
    return r


def _fetch_video(url, out_dir="/tmp/dl"):
    """yt-dlp with the same resilience ladder as the production fetcher."""
    os.makedirs(out_dir, exist_ok=True)
    tpl = os.path.join(out_dir, "clip.%(ext)s")
    base = ["yt-dlp", "--no-playlist", "-f", "bv*+ba/b", "-S", "vcodec:h264,acodec:m4a",
            "--merge-output-format", "mp4", "--force-ipv4", "--no-warnings", "-o", tpl]
    last = None
    for cmd in (base + [url], base + [url], base + ["--impersonate", "chrome", url]):
        try:
            _run(cmd)
            break
        except RuntimeError as e:
            last = e
    else:
        raise last
    for f in os.listdir(out_dir):
        if f.endswith(".mp4"):
            return os.path.join(out_dir, f)
    raise RuntimeError("download produced no mp4")


def _prep_media(item):
    """Return a normalized mp4 path: stills loop for 12s with silent audio,
    videos are capped at 120s and re-encoded to h264/aac."""
    if item["kind"] == "image":
        src = "/tmp/still.jpg"
        open(src, "wb").write(base64.b64decode(item["b64"]))
        out = "/tmp/still.mp4"
        _run(["ffmpeg", "-y", "-loop", "1", "-i", src,
              "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "12",
              "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out])
        return out
    raw = _fetch_video(item["url"])
    out = "/tmp/clip_norm.mp4"
    _run(["ffmpeg", "-y", "-i", raw, "-t", "120", "-c:v", "libx264",
          "-pix_fmt", "yuv420p", "-c:a", "aac", out])
    return out


@app.cls(gpu="A100", volumes={"/cache": cache}, secrets=_secrets,
         timeout=3600, scaledown_window=240)
class Tribe:
    @modal.enter()
    def load(self):
        import urllib.request

        import nibabel.freesurfer as fs
        import numpy as np
        from tribev2 import TribeModel

        os.makedirs("/cache/atlas", exist_ok=True)
        labels = []
        for h in ("lh", "rh"):
            p = f"/cache/atlas/{h}.annot"
            if not os.path.exists(p):
                urllib.request.urlretrieve(_CBIG.format(h=h), p)
            lab, _, names = fs.read_annot(p)
            names = [n.decode() for n in names]
            # parcel name -> network token, e.g. 7Networks_LH_Vis_1 -> Vis
            nets = [n.split("_")[2] if n.startswith("7Networks") else "None" for n in names]
            labels.append(np.array([nets[v] for v in lab]))
        # TRIBE v2 predicts fsaverage5 vertices ordered lh then rh.
        self.vertex_net = np.concatenate(labels)
        self.model = TribeModel.from_pretrained("facebook/tribev2", cache_folder="/cache/hf")
        cache.commit()

    @modal.method()
    def extract(self, item):
        import numpy as np
        try:
            path = _prep_media(item)
            df = self.model.get_events_dataframe(video_path=path)
            preds, _segments = self.model.predict(events=df)
            preds = np.asarray(preds, dtype=np.float64)
            T, V = preds.shape
            net_map = self.vertex_net
            if V != net_map.shape[0]:
                raise RuntimeError(f"vertex count {V} != atlas {net_map.shape[0]}")
            k = max(1, round(T * 0.2))
            feats = {"n_timesteps": int(T), "global_mean": float(preds.mean()),
                     "global_std": float(preds.std())}
            for net in NETWORKS:
                ts = preds[:, net_map == net].mean(axis=1)
                feats[f"{net}_mean"] = float(ts.mean())
                feats[f"{net}_peak"] = float(ts.max())
                feats[f"{net}_std"] = float(ts.std())
                feats[f"{net}_early"] = float(ts[:k].mean())
                feats[f"{net}_late"] = float(ts[-k:].mean())
            return {"id": item["id"], "kind": item["kind"], "ok": True, "features": feats}
        except Exception as e:
            return {"id": item["id"], "kind": item["kind"], "ok": False, "error": str(e)[-500:]}


@app.local_entrypoint()
def main(smoke: bool = False, only_kind: str = "", limit: int = 0):
    here = os.path.dirname(os.path.abspath(__file__))
    manifest = json.load(open(os.path.join(here, "manifest.json"), encoding="utf-8"))
    out_path = os.path.join(here, "features.json")
    done = {}
    if os.path.exists(out_path):
        done = {r["id"]: r for r in json.load(open(out_path, encoding="utf-8")) if r.get("ok")}

    items = [i for i in manifest if i["id"] not in done]
    if only_kind:
        items = [i for i in items if i["kind"] == only_kind]
    if smoke:
        imgs = [i for i in items if i["kind"] == "image"][:2]
        vids = [i for i in items if i["kind"] == "video"][:1]
        items = imgs + vids
    if limit:
        items = items[:limit]

    payloads = []
    for i in items:
        if i["kind"] == "image":
            b = open(os.path.join(here, "..", "..", *i["path"].split("/")), "rb").read()
            payloads.append({**i, "b64": base64.b64encode(b).decode()})
        else:
            payloads.append(i)

    print(f"extracting {len(payloads)} items ({len(done)} already done)")
    results = list(done.values())
    for r in Tribe().extract.map(payloads, return_exceptions=True):
        if isinstance(r, Exception):
            print("worker exception:", str(r)[:200])
            continue
        results.append(r)
        tag = "ok" if r["ok"] else f"FAIL {r.get('error', '')[:80]}"
        print(f"  {r['id'][:8]} [{r['kind']}] {tag}")
        json.dump(results, open(out_path, "w", encoding="utf-8"), indent=1)

    n_ok = sum(1 for r in results if r.get("ok"))
    print(f"done: {n_ok}/{len(results)} ok -> {out_path}")
