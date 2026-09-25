"""Functional reimplementation of extract_keyframes.py (original lives only on
the currently-unreachable Modal volume).

Reproduces the output contract consumed by diagnose_video_v5.run_diagnosis and
cognitive_kpis:
  - "duration_sec": float
  - "key_frames": [{"timestamp", "composite_score", "motion_norm", "frame_path"}]
  - "score_timeline": [{"t": <sec>, "score": <0-10>}]  (one point per second)

Scores are a 0-10 composite of per-second motion, sharpness, contrast, and
edge density, min-max normalized across the video. Swap the original back in
once the Modal volume is recovered (`modal volume get fixation-assets`).
"""

import os
import cv2
import numpy as np


def _frame_metrics(frame_bgr, prev_gray):
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (160, 90))
    sharpness = float(cv2.Laplacian(small, cv2.CV_64F).var())
    contrast = float(small.std())
    edges = cv2.Canny(small, 100, 200)
    edge_density = float((edges > 0).mean())
    motion = float(np.mean(cv2.absdiff(small, prev_gray))) if prev_gray is not None else 0.0
    return small, {"motion": motion, "sharpness": sharpness,
                   "contrast": contrast, "edge_density": edge_density}


def _normalize(values):
    arr = np.asarray(values, dtype=np.float64)
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-8:
        return np.full_like(arr, 0.5)
    return (arr - lo) / (hi - lo)


def extract_keyframes(video_path, output_dir, num_frames=4):
    os.makedirs(output_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    duration = total / fps if fps else 0.0

    seconds = max(1, int(duration))
    sampled = []          # (t, frame_bgr, metrics)
    prev_gray = None
    for s in range(seconds):
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(int(s * fps), max(total - 1, 0)))
        ok, frame = cap.read()
        if not ok:
            continue
        prev_gray, metrics = _frame_metrics(frame, prev_gray)
        sampled.append((float(s), frame, metrics))
    cap.release()

    if not sampled:
        return {"video_path": video_path, "duration_sec": round(duration, 2),
                "fps": fps, "key_frames": [], "score_timeline": []}

    motion_n = _normalize([m["motion"] for _, _, m in sampled])
    sharp_n = _normalize([m["sharpness"] for _, _, m in sampled])
    contrast_n = _normalize([m["contrast"] for _, _, m in sampled])
    edge_n = _normalize([m["edge_density"] for _, _, m in sampled])
    composite = (0.35 * motion_n + 0.25 * sharp_n + 0.20 * contrast_n + 0.20 * edge_n) * 10.0

    score_timeline = [{"t": t, "score": round(float(c), 2)}
                      for (t, _, _), c in zip(sampled, composite)]

    order = np.argsort(-composite)
    key_frames = []
    for idx in order[:max(1, num_frames)]:
        t, frame, _ = sampled[idx]
        path = os.path.join(output_dir, f"keyframe_t{t:05.1f}s.jpg")
        cv2.imwrite(path, frame)
        key_frames.append({
            "timestamp": round(t, 2),
            "composite_score": round(float(composite[idx]), 2),
            "motion_norm": round(float(motion_n[idx]), 3),
            "frame_path": path,
        })
    key_frames.sort(key=lambda k: k["timestamp"])

    return {
        "video_path": video_path,
        "duration_sec": round(duration, 2),
        "fps": round(float(fps), 2),
        "num_sampled": len(sampled),
        "key_frames": key_frames,
        "score_timeline": score_timeline,
    }
