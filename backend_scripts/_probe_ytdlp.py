"""One-off probe: verify yt-dlp behaviour from inside Modal's network.
Run: modal run backend_scripts/_probe_ytdlp.py
"""
import modal

image = (
    modal.Image.debian_slim()
    .pip_install("yt-dlp", "curl-cffi")
    .run_commands("apt-get update && apt-get install -y ffmpeg")
    .run_commands("pip install --no-cache-dir --upgrade yt-dlp curl-cffi  # 2026-08-26b")
)
vol = modal.Volume.from_name("fixation-assets")
app = modal.App("probe-ytdlp", image=image)

TIKTOK_URL = "https://www.tiktok.com/@tiktok/video/7676062295977413904"


@app.function(volumes={"/mnt/fixation-assets": vol}, timeout=600)
def probe():
    import subprocess

    base = ["yt-dlp", "--no-playlist", "-f", "bv*+ba/b",
            "-S", "vcodec:h264,acodec:m4a", "--merge-output-format", "mp4",
            "--force-ipv4", "--no-warnings", "-o", "/tmp/probe-tt.%(ext)s"]

    r1 = subprocess.run(base + [TIKTOK_URL], capture_output=True, text=True)
    print("=== plain rc:", r1.returncode)
    print("ERR1:", r1.stderr[-600:])

    r2 = subprocess.run(base + ["--impersonate", "chrome", TIKTOK_URL],
                        capture_output=True, text=True)
    print("=== impersonate rc:", r2.returncode)
    print("ERR2:", r2.stderr[-600:])

    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=index,codec_type,codec_name", "-of", "csv=p=0", "/tmp/probe-tt.mp4"],
        capture_output=True, text=True,
    )
    print("=== streams:", p.stdout, p.stderr)
