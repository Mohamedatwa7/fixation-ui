"""One-off: introspect the tribev2 API for modality controls.
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
    .pip_install("torchaudio==2.6.0")
)

app = modal.App("tribe-api-probe", image=image)


@app.function(timeout=600)
def probe():
    import inspect

    from tribev2 import TribeModel

    for name in ("from_pretrained", "get_events_dataframe", "predict"):
        fn = getattr(TribeModel, name, None)
        if fn is None:
            print(name, ": MISSING")
            continue
        try:
            print(f"--- {name}{inspect.signature(fn)}")
        except Exception as e:
            print(f"--- {name}: signature failed {e}")
    try:
        src = inspect.getsource(TribeModel.get_events_dataframe)
        print(src[:4000])
    except Exception as e:
        print("source failed:", e)
