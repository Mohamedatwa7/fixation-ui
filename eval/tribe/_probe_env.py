"""One-off: inspect CUDA runtime libs inside the TRIBE image.
Run: python -m modal run eval/tribe/_probe_env.py
"""
import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install("torch", "torchvision", "torchaudio")
    .pip_install(
        "git+https://github.com/facebookresearch/tribev2.git",
        "nibabel", "pandas", "huggingface_hub", "yt-dlp", "curl-cffi",
    )
    .pip_install("nvidia-cuda-runtime")
    .env({"LD_LIBRARY_PATH":
          "/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib"})
)

app = modal.App("tribe-env-probe", image=image)


@app.function(gpu="A100", timeout=600)
def probe():
    import glob
    import os
    import subprocess

    print("LD_LIBRARY_PATH =", os.environ.get("LD_LIBRARY_PATH"))
    hits = glob.glob("/usr/local/lib/python3.11/site-packages/**/libcudart*",
                     recursive=True)
    print("libcudart in site-packages:", hits or "NONE")
    sys_hits = subprocess.run(["find", "/usr", "-name", "libcudart*"],
                              capture_output=True, text=True).stdout.strip()
    print("libcudart under /usr:", sys_hits or "NONE")
    for mod in ("torch", "torchaudio", "torchcodec", "torchvision"):
        try:
            m = __import__(mod)
            print(mod, "ok", getattr(m, "__version__", "?"))
        except Exception as e:
            print(mod, "FAIL:", str(e)[:250])
    import torch
    print("torch cuda:", torch.version.cuda, "available:", torch.cuda.is_available())
