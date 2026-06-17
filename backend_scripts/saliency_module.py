"""Saliency module wrapping TASED-Net for per-frame gaze prediction."""

import os
import json
import numpy as np
import cv2

TASED_INPUT_SIZE = (224, 384)
TASED_CLIP_LEN = 32
TASED_FRAME_OFFSET = 31


def load_tased_model(weights_path, device="cuda"):
    import sys, torch
    tased_repo = "/content/TASED-Net"
    if tased_repo not in sys.path:
        sys.path.insert(0, tased_repo)
    from model import TASED_v2
    print(f"Loading TASED-Net from {weights_path}...")
    model = TASED_v2()
    weights = torch.load(weights_path, map_location=device, weights_only=False)
    if "model_state_dict" in weights:
        weights = weights["model_state_dict"]
    # Strip DataParallel "module." prefix that was added during multi-GPU training
    weights = {k.replace("module.", "", 1) if k.startswith("module.") else k: v
               for k, v in weights.items()}
    # Now load STRICT so any future mismatch raises loudly instead of failing silently
    model.load_state_dict(weights, strict=True)
    model = model.to(device).eval()
    print("TASED-Net loaded.")
    return model


def read_video_frames(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return frames, float(fps)


def preprocess_clip(frames, target_size=TASED_INPUT_SIZE):
    import torch
    H, W = target_size
    processed = []
    for f in frames:
        resized = cv2.resize(f, (W, H))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        processed.append(rgb.astype(np.float32) / 255.0)
    arr = np.stack(processed, axis=0).transpose(3, 0, 1, 2)
    return torch.from_numpy(arr).unsqueeze(0)


def run_tased_inference(model, frames, device="cuda"):
    import torch
    n = len(frames)
    padded = [frames[0]] * TASED_FRAME_OFFSET + list(frames)
    saliency_maps = []
    print(f"  Running TASED inference on {n} frames...")
    with torch.no_grad():
        for i in range(n):
            clip = padded[i:i + TASED_CLIP_LEN]
            tensor = preprocess_clip(clip).to(device)
            sal = model(tensor)
            sal_np = sal.squeeze().cpu().numpy()
            saliency_maps.append(sal_np)
            if i % 20 == 0:
                print(f"    frame {i}/{n}")
    return saliency_maps


def normalize_saliency(sal_map):
    smin, smax = sal_map.min(), sal_map.max()
    if smax - smin < 1e-8:
        return np.zeros_like(sal_map, dtype=np.uint8)
    return (255.0 * (sal_map - smin) / (smax - smin)).astype(np.uint8)


def overlay_heatmap(frame_bgr, sal_map, alpha=0.5):
    H, W = frame_bgr.shape[:2]
    sal_resized = cv2.resize(sal_map, (W, H))
    sal_u8 = normalize_saliency(sal_resized)
    heatmap = cv2.applyColorMap(sal_u8, cv2.COLORMAP_JET)
    return cv2.addWeighted(frame_bgr, 1.0 - alpha, heatmap, alpha, 0)


def write_overlay_video(frames, saliency_maps, fps, output_path):
    if not frames:
        return None
    H, W = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (W, H))
    for f, s in zip(frames, saliency_maps):
        writer.write(overlay_heatmap(f, s))
    writer.release()
    print(f"  Overlay video saved to {output_path}")
    return output_path


def extract_gaze_region(sal_map, frame_shape):
    H_f, W_f = frame_shape[:2]
    sal_resized = cv2.resize(sal_map, (W_f, H_f))
    sal_pos = np.maximum(sal_resized, 0)
    total = sal_pos.sum()
    if total < 1e-8:
        return {"x": W_f // 2, "y": H_f // 2, "zone": "center", "confidence_ratio": 0.0}
    ys, xs = np.indices(sal_resized.shape)
    cx = float((xs * sal_pos).sum() / total)
    cy = float((ys * sal_pos).sum() / total)
    col = "left" if cx < W_f / 3 else "right" if cx > 2 * W_f / 3 else "center-x"
    row = "top" if cy < H_f / 3 else "bottom" if cy > 2 * H_f / 3 else "middle"
    zone = "center" if (col == "center-x" and row == "middle") else f"{row}-{col.replace('center-x','center')}"
    peak = float(sal_pos.max())
    confidence = peak / (sal_pos.mean() + 1e-8)
    return {"x": round(cx, 1), "y": round(cy, 1), "zone": zone,
            "confidence_ratio": round(confidence, 2)}


def analyze_saliency(video_path, tased_weights_path, output_dir,
                     keyframe_timestamps=None, device=None):
    import torch
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    os.makedirs(output_dir, exist_ok=True)
    print(f"Reading {video_path}...")
    frames, fps = read_video_frames(video_path)
    if not frames:
        return {"error": "No frames could be read"}
    print(f"  {len(frames)} frames at {fps:.1f} fps")
    model = load_tased_model(tased_weights_path, device=device)
    saliency_maps = run_tased_inference(model, frames, device=device)
    del model
    torch.cuda.empty_cache()
    gaze_per_frame = [extract_gaze_region(s, frames[0].shape) for s in saliency_maps]
    if keyframe_timestamps is None:
        keyframe_timestamps = list(np.arange(0, len(frames) / fps, 1.0))
    gaze_at_keyframes = []
    for ts in keyframe_timestamps:
        idx = min(int(ts * fps), len(gaze_per_frame) - 1)
        gaze_data = gaze_per_frame[idx].copy()
        gaze_data["timestamp"] = round(float(ts), 2)
        gaze_at_keyframes.append(gaze_data)
    overlay_path = os.path.join(output_dir, "saliency_overlay.mp4")
    write_overlay_video(frames, saliency_maps, fps, overlay_path)
    sample_dir = os.path.join(output_dir, "saliency_frames")
    os.makedirs(sample_dir, exist_ok=True)
    for ts in keyframe_timestamps:
        idx = min(int(ts * fps), len(frames) - 1)
        overlay = overlay_heatmap(frames[idx], saliency_maps[idx])
        cv2.imwrite(os.path.join(sample_dir, f"saliency_t{ts:05.2f}s.png"), overlay)
    summary = _summarize_for_diagnosis(gaze_at_keyframes, len(frames), fps)
    metadata = {
        "video_path": video_path, "fps": fps,
        "total_frames": len(frames), "duration_sec": len(frames) / fps,
        "overlay_video": overlay_path, "sample_frames_dir": sample_dir,
        "gaze_at_keyframes": gaze_at_keyframes,
        "diagnostic_summary": summary,
    }
    with open(os.path.join(output_dir, "saliency_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2, cls=_NumpyJSONEncoder)
    print(f"Saliency metadata saved")
    return metadata


class _NumpyJSONEncoder(json.JSONEncoder):
    """Handles numpy types that the default JSON encoder chokes on."""
    def default(self, o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def _summarize_for_diagnosis(gaze_at_keyframes, total_frames, fps):
    lines = ["Predicted gaze location per second (from TASED-Net):"]
    zone_counts = {}
    for g in gaze_at_keyframes:
        zone_counts[g["zone"]] = zone_counts.get(g["zone"], 0) + 1
    total = sum(zone_counts.values())
    if total > 0:
        lines.append("\nGaze zone distribution:")
        for zone, count in sorted(zone_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {zone}: {100*count/total:.0f}% of frames")
    lines.append("\nPer-second gaze trajectory:")
    for g in gaze_at_keyframes[:30]:
        lines.append(f"  t={g['timestamp']}s -> {g['zone']} "
                     f"(focus_strength={g['confidence_ratio']:.1f})")
    if len(gaze_at_keyframes) > 30:
        lines.append(f"  ... ({len(gaze_at_keyframes)-30} more points)")
    if len(gaze_at_keyframes) > 1:
        zones = [g["zone"] for g in gaze_at_keyframes]
        transitions = sum(1 for i in range(1, len(zones)) if zones[i] != zones[i-1])
        lines.append(f"\nGaze stability: {len(set(zones))} distinct zones, "
                     f"{transitions} zone transitions")
    return "\n".join(lines)
