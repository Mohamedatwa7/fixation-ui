"""One-off probe: verify the volume's fetch_video.py and yt-dlp's view of
YouTube from inside Modal's network. Run: modal run backend_scripts/_probe_ytdlp.py
"""
import modal

image = (
    modal.Image.debian_slim()
    .pip_install("yt-dlp")
    .run_commands("apt-get update && apt-get install -y ffmpeg")
    .run_commands("pip install --no-cache-dir --upgrade yt-dlp  # 2026-08-26")
)
vol = modal.Volume.from_name("fixation-assets")
app = modal.App("probe-ytdlp", image=image)

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@app.function(volumes={"/mnt/fixation-assets": vol}, timeout=600)
def probe():
    import hashlib
    import subprocess

    src = open("/mnt/fixation-assets/fetch_video.py").read()
    print("VOLUME fetch_video.py md5:", hashlib.md5(src.encode()).hexdigest())
    print("HAS vcodec sort:", "vcodec:h264" in src)
    print("HAS retry ladder:", "player_client=android" in src)

    r = subprocess.run(
        ["yt-dlp", "-F", "--force-ipv4", "--no-warnings", URL],
        capture_output=True, text=True,
    )
    print("=== yt-dlp -F rc:", r.returncode)
    print(r.stdout[-4000:])
    print("ERR:", r.stderr[-1500:])

    r2 = subprocess.run(
        ["yt-dlp", "--no-playlist", "-f", "bv*+ba/b",
         "-S", "vcodec:h264,acodec:m4a", "--merge-output-format", "mp4",
         "--force-ipv4", "--no-warnings", "-o", "/tmp/probe.%(ext)s", URL],
        capture_output=True, text=True,
    )
    print("=== download rc:", r2.returncode)
    print("ERR:", r2.stderr[-1500:])
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=index,codec_type,codec_name", "-of", "csv=p=0", "/tmp/probe.mp4"],
        capture_output=True, text=True,
    )
    print("=== streams:", p.stdout, p.stderr)
