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

    cmd = [
        "yt-dlp", "--no-playlist", "-f", "mp4/best[ext=mp4]/best",
        "--write-info-json", "--no-warnings", "--quiet", "--progress",
        "-o", output_template, url,
    ]
    print(f"Fetching from {platform}: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": "yt-dlp failed", "stdout": result.stdout, "stderr": result.stderr}

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
