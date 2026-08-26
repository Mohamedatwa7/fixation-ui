"""Multi-platform video fetcher using yt-dlp."""

import os
import json
import subprocess
import re


def detect_platform(url):
    u = url.lower()
    if "tiktok.com" in u: return "tiktok"
    if "instagram.com" in u: return "instagram"
    if "youtube.com" in u or "youtu.be" in u: return "youtube"
    if "twitter.com" in u or "x.com" in u: return "twitter"
    if "facebook.com" in u or "fb.watch" in u: return "facebook"
    return "unknown"


def fetch_video(url, output_dir="/content/fetched_videos", filename_prefix=None):
    os.makedirs(output_dir, exist_ok=True)
    platform = detect_platform(url)
    if filename_prefix is None:
        filename_prefix = re.sub(r"[^a-zA-Z0-9_]", "_", url.split("/")[-1])[:40]
    output_template = os.path.join(output_dir, f"{filename_prefix}.%(ext)s")

    # Merge best video + audio explicitly: YouTube's adaptive streams are
    # split, and a bare "best" can land a video-only file that kills the audio
    # stage. Prefer h264/m4a — the analysis pipeline can't decode AV1.
    base = [
        "yt-dlp", "--no-playlist", "-f", "bv*+ba/b",
        "-S", "vcodec:h264,acodec:m4a",
        "--merge-output-format", "mp4",
        "--write-info-json", "--no-warnings", "--quiet", "--progress",
        "--force-ipv4", "-o", output_template,
    ]
    # Retry ladder: datacenter IPs trip bot checks that a retry or a browser
    # TLS fingerprint (--impersonate, via curl-cffi) usually clears. TikTok's
    # "Unexpected response from webpage request" in particular is transient.
    attempts = [
        base + [url],
        base + [url],
        base + ["--impersonate", "chrome", url],
    ]
    if platform == "youtube":
        attempts += [
            base + ["--extractor-args", "youtube:player_client=android", url],
            base + ["--extractor-args", "youtube:player_client=ios", url],
        ]
    print(f"Fetching from {platform}: {url}")
    result = None
    for cmd in attempts:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            break
    if result is None or result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-400:] if result else ""
        return {
            "error": f"yt-dlp failed: {tail}" if tail else "yt-dlp failed",
            "stdout": result.stdout if result else "",
            "stderr": result.stderr if result else "",
        }

    video_path = None
    info_path = None
    for f in os.listdir(output_dir):
        full = os.path.join(output_dir, f)
        if f.startswith(filename_prefix):
            if f.endswith(".info.json"):
                info_path = full
            elif f.endswith((".mp4", ".mkv", ".webm", ".mov")):
                video_path = full

    if not video_path:
        return {"error": "Downloaded file not found", "looked_in": output_dir}

    # Photo/slideshow posts download as audio-only; fail early with a clear
    # message instead of crashing the analysis pipeline downstream.
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
        capture_output=True, text=True,
    )
    if probe.returncode == 0 and "video" not in probe.stdout:
        return {"error": "The URL has no video stream (photo/slideshow post?) — use a video post"}

    metadata = {}
    if info_path and os.path.exists(info_path):
        with open(info_path) as f:
            info = json.load(f)
        metadata = {
            "title": info.get("title") or info.get("description", "")[:80],
            "description": info.get("description"),
            "uploader": info.get("uploader") or info.get("channel"),
            "uploader_url": info.get("uploader_url"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "comment_count": info.get("comment_count"),
            "duration_sec": info.get("duration"),
            "upload_date": info.get("upload_date"),
            "tags": info.get("tags"),
        }

    if not video_path.endswith(".mp4"):
        clean_path = os.path.splitext(video_path)[0] + "_clean.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264",
                       "-c:a", "aac", "-loglevel", "error", clean_path], check=True)
        video_path = clean_path

    return {
        "video_path": video_path, "platform": platform,
        "original_url": url, **metadata,
    }


def fetch_and_analyze(url, output_dir="/content/reports", **kwargs):
    os.makedirs(output_dir, exist_ok=True)
    fetched = fetch_video(url)
    if "error" in fetched:
        return fetched
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_",
                     fetched["original_url"].split("/")[-1])[:40]
    report_path = os.path.join(output_dir, f"{fetched['platform']}_{safe_id}.json")
    cmd = ["python", "/content/diagnose_video_v5.py",
           "--video-path", fetched["video_path"], "--output", report_path]
    title = fetched.get("title")
    description = fetched.get("description")
    if title: cmd.extend(["--title", title])
    if description:
        clean_desc = " ".join(description.split())[:500]
        cmd.extend(["--description", clean_desc])
    print(f"\nRunning diagnostic on {fetched['video_path']}...")
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    subprocess.run(cmd, env=env)
    return {"fetched": fetched, "report_path": report_path}
