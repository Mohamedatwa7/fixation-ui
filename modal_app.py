import modal
import os
import json
import base64
import subprocess
import uuid
import threading

# GPU image with all deps + ffmpeg
image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi", "uvicorn", "python-multipart",
        "torch", "torchvision", "transformers", "qwen-vl-utils", "accelerate",
        "opencv-contrib-python", "numpy", "librosa", "openai-whisper",
        "yt-dlp", "anthropic", "Pillow", "scipy",
    )
    .run_commands("apt-get update && apt-get install -y ffmpeg")
)

assets_volume = modal.Volume.from_name("fixation-assets")
hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)

app = modal.App(name="fixation-api", image=image)

# Paths inside the container
SCRIPTS_DIR = "/mnt/fixation-assets"                    # scripts now live at root
NESTED = "/mnt/fixation-assets/fixation-assets"         # weights/benchmarks are nested here
TASED_WEIGHTS = f"{NESTED}/tased_weights/TASED_updated.pt"
BENCHMARK = f"{NESTED}/benchmarks/benchmark_advert_gallery_percentiles.json"
TASED_REPO = f"{NESTED}/TASED-Net"                      # saliency_module hardcodes /content/TASED-Net
MODEL_CACHE = "/hf-cache"


def _setup_paths():
    """saliency_module.py hardcodes /content/TASED-Net; symlink it to the real repo."""
    os.makedirs("/content", exist_ok=True)
    link = "/content/TASED-Net"
    if not os.path.islink(link) and not os.path.exists(link):
        os.symlink(TASED_REPO, link, target_is_directory=True)


@app.function(
    gpu="A10G",
    volumes={"/mnt/fixation-assets": assets_volume, "/hf-cache": hf_cache},
    timeout=1800,
    secrets=[modal.Secret.from_name("anthropic")],
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, File, UploadFile, Form
    import sys
    sys.path.insert(0, SCRIPTS_DIR)
    _setup_paths()

    web_app = FastAPI()
    JOBS = {}

    def b64(path):
        if not path or not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @web_app.post("/api/analyze/image")
    async def analyze_image_endpoint(
        file: UploadFile = File(...),
        title: str = Form(None), description: str = Form(None),
        format_type: str = Form("KV"), role: str = Form("creative_director"),
    ):
        tmp = f"/tmp/upload_{file.filename}"
        with open(tmp, "wb") as f:
            f.write(await file.read())
        try:
            from analyze_image import analyze_image
            report = analyze_image(
                image_path=tmp,
                title=title or None,
                description=description or None,
                format_type=format_type,
                output_path="/tmp/image_report.json",
                model_cache=MODEL_CACHE,
                benchmark_path=BENCHMARK,
                role_key=role,
            )
            overlay = report.get("saliency", {}).get("overlay_path")
            kpi_data = report.get("kpis", {})
            return {
                "verdict": report.get("diagnosis", {}),
                "score": kpi_data.get("overall", 0),
                "kpis": kpi_data.get("kpis", {}),
                "kpis_overall": kpi_data.get("overall", 0),
                "funnel_stage": kpi_data.get("funnel_stage"),
                "product_tier": kpi_data.get("product_tier"),
                "localization": report.get("localization"),
                "heatmap": b64(overlay),
                "heatmap_type": "image/png",
            }
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[-800:]}
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def _run_image(job_id, image_path, title, description, format_type, role):
        try:
            JOBS[job_id] = {"status": "analyzing"}
            from analyze_image import analyze_image
            report = analyze_image(
                image_path=image_path,
                title=title or None,
                description=description or None,
                format_type=format_type,
                output_path=f"/tmp/image_report_{job_id}.json",
                model_cache=MODEL_CACHE,
                benchmark_path=BENCHMARK,
                role_key=role,
            )
            overlay = report.get("saliency", {}).get("overlay_path")
            kpi_data = report.get("kpis", {})
            JOBS[job_id] = {
                "status": "done",
                "result": {
                    "verdict": report.get("diagnosis", {}),
                    "score": kpi_data.get("overall", 0),
                    "kpis": kpi_data.get("kpis", {}),
                    "kpis_overall": kpi_data.get("overall", 0),
                    "funnel_stage": kpi_data.get("funnel_stage"),
                    "product_tier": kpi_data.get("product_tier"),
                    "localization": report.get("localization"),
                    "heatmap": b64(overlay),
                    "heatmap_type": "image/png",
                },
            }
        except Exception as e:
            import traceback
            JOBS[job_id] = {"status": "error", "error": str(e), "trace": traceback.format_exc()[-800:]}
        finally:
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass

    def _run_video(job_id, video_path):
        try:
            JOBS[job_id] = {"status": "analyzing"}
            out = f"/tmp/video_{job_id}.json"
            cmd = [
                "python", f"{SCRIPTS_DIR}/diagnose_video_v5.py",
                "--video-path", video_path,
                "--output", out,
                "--model-cache", MODEL_CACHE,
                "--tased-weights", TASED_WEIGHTS,
            ]
            env = os.environ.copy()
            env["MPLBACKEND"] = "Agg"
            env["PYTHONPATH"] = f"{SCRIPTS_DIR}:{TASED_REPO}"
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500, env=env)
            if r.returncode != 0 or not os.path.exists(out):
                JOBS[job_id] = {"status": "error", "error": (r.stderr or "no output")[-1200:]}
                return
            with open(out) as f:
                report = json.load(f)

            kpis_block = {}
            overall = 0
            try:
                sys.path.insert(0, SCRIPTS_DIR)
                from cognitive_kpis import compute_cognitive_kpis
                kpi_data = compute_cognitive_kpis(report)
                kpis_block = kpi_data.get("kpis", {})
                overall = kpi_data.get("overall", 0)
            except Exception as ke:
                print(f"KPI computation failed: {ke}")

            sal = report.get("saliency", {}).get("overlay_video")
            sal_web = None
            if sal and os.path.exists(sal):
                sal_web = sal + "_web.mp4"
                tx = subprocess.run(
                    ["ffmpeg", "-y", "-i", sal, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-movflags", "+faststart", "-an", sal_web],
                    capture_output=True, text=True,
                )
                if tx.returncode != 0 or not os.path.exists(sal_web):
                    print(f"ffmpeg transcode failed: {tx.stderr[-400:]}")
                    sal_web = sal
            JOBS[job_id] = {
                "status": "done",
                "result": {
                    "verdict": report.get("diagnosis", {}),
                    "score": overall,
                    "kpis": kpis_block,
                    "kpis_overall": overall,
                    "heatmap": b64(sal_web),
                    "heatmap_type": "video/mp4",
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

    @web_app.post("/api/analyze/video-url/submit")
    async def submit_video_url(url: str = Form(...), role: str = Form("creative_director")):
        job_id = str(uuid.uuid4())
        JOBS[job_id] = {"status": "fetching"}

        def work():
            try:
                import fetch_video
                fetched = fetch_video.fetch_video(url)
                if "error" in fetched:
                    JOBS[job_id] = {"status": "error", "error": fetched.get("error")}
                    return
                _run_video(job_id, fetched["video_path"])
            except Exception as e:
                JOBS[job_id] = {"status": "error", "error": str(e)}

        threading.Thread(target=work, daemon=True).start()
        return {"job_id": job_id}

    @web_app.post("/api/analyze/image/submit")
    async def submit_image(
        file: UploadFile = File(...),
        title: str = Form(None), description: str = Form(None),
        format_type: str = Form("KV"), role: str = Form("creative_director"),
    ):
        job_id = str(uuid.uuid4())
        tmp = f"/tmp/upload_{job_id}_{file.filename}"
        with open(tmp, "wb") as f:
            f.write(await file.read())
        JOBS[job_id] = {"status": "analyzing"}
        threading.Thread(
            target=_run_image,
            args=(job_id, tmp, title, description, format_type, role),
            daemon=True,
        ).start()
        return {"job_id": job_id}

    @web_app.post("/api/analyze/video/submit")
    async def submit_video_file(file: UploadFile = File(...), role: str = Form("creative_director")):
        job_id = str(uuid.uuid4())
        tmp = f"/tmp/upload_{job_id}_{file.filename}"
        with open(tmp, "wb") as f:
            f.write(await file.read())
        threading.Thread(target=_run_video, args=(job_id, tmp), daemon=True).start()
        return {"job_id": job_id}

    @web_app.get("/api/job/{job_id}")
    async def job_status(job_id: str):
        return JOBS.get(job_id, {"status": "not_found"})

    @web_app.get("/health")
    async def health():
        return {"status": "ok"}

    return web_app
