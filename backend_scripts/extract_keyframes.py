"""Key-frame extraction: scores frames by motion + edges + entropy, saves top N."""

import os
import json
import cv2
import numpy as np


def compute_entropy(gray_frame):
    hist, _ = np.histogram(gray_frame, bins=256, range=(0, 256))
    hist = hist / (hist.sum() + 1e-8)
    hist = hist[hist > 0]
    return -np.sum(hist * np.log2(hist))


def compute_edge_density(gray_frame):
    return cv2.Laplacian(gray_frame, cv2.CV_64F).var()


def compute_motion(prev_gray, curr_gray):
    if prev_gray is None:
        return 0.0
    return float(cv2.absdiff(prev_gray, curr_gray).mean())


def score_frames(video_path, sample_fps=2.0):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / native_fps
    sample_every = max(1, int(native_fps / sample_fps))
    results = []
    prev_gray = None
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_every == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            results.append({
                "timestamp": frame_idx / native_fps,
                "frame_idx": frame_idx,
                "entropy": float(compute_entropy(gray)),
                "edges": float(compute_edge_density(gray)),
                "motion": compute_motion(prev_gray, gray),
                "frame_bgr": frame,
            })
            prev_gray = gray
        frame_idx += 1
    cap.release()
    return results, duration_sec


def extract_keyframes(video_path, output_dir, num_frames=4, sample_fps=2.0, min_gap_sec=1.0):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Scoring frames in {video_path}...")
    frames, duration_sec = score_frames(video_path, sample_fps=sample_fps)
    if not frames:
        return {"error": "No frames could be extracted"}
    for signal in ("entropy", "edges", "motion"):
        vals = np.array([f[signal] for f in frames])
        vmin, vmax = vals.min(), vals.max()
        if vmax > vmin:
            for f in frames:
                f[f"{signal}_norm"] = 10.0 * (f[signal] - vmin) / (vmax - vmin)
        else:
            for f in frames:
                f[f"{signal}_norm"] = 0.0
    for f in frames:
        f["composite_score"] = (
            0.25 * f["entropy_norm"] + 0.25 * f["edges_norm"] + 0.50 * f["motion_norm"]
        )
    candidates = sorted(frames, key=lambda f: f["composite_score"], reverse=True)
    selected = []
    for cand in candidates:
        if len(selected) >= num_frames:
            break
        if all(abs(cand["timestamp"] - s["timestamp"]) >= min_gap_sec for s in selected):
            selected.append(cand)
    selected.sort(key=lambda f: f["timestamp"])
    metadata = {
        "video_path": video_path,
        "duration_sec": round(duration_sec, 2),
        "total_frames_scored": len(frames),
        "sample_fps": sample_fps,
        "key_frames": [],
    }
    for rank, f in enumerate(selected):
        ts = f["timestamp"]
        fname = f"keyframe_{rank:02d}_t{ts:05.2f}s_score{f['composite_score']:.1f}.png"
        fpath = os.path.join(output_dir, fname)
        cv2.imwrite(fpath, f["frame_bgr"])
        metadata["key_frames"].append({
            "rank": rank,
            "timestamp": round(ts, 2),
            "filename": fname,
            "path": fpath,
            "composite_score": round(f["composite_score"], 2),
            "entropy_norm": round(f["entropy_norm"], 2),
            "edges_norm": round(f["edges_norm"], 2),
            "motion_norm": round(f["motion_norm"], 2),
        })
        print(f"  -> Saved {fname}")
    metadata["score_timeline"] = [
        {"t": round(f["timestamp"], 2), "score": round(f["composite_score"], 2)}
        for f in frames
    ]
    meta_path = os.path.join(output_dir, "keyframes_metadata.json")
    with open(meta_path, "w") as fh:
        json.dump(metadata, fh, indent=2)
    print(f"Saved metadata to {meta_path}")
    return metadata
