"""AAM (Attend to Anything, ICML 2026) saliency wrapper.

Drop-in upgrade for the OpenCV static saliency (images) and TASED-Net
(video) stages. Model: DINOv3 ViT-L backbone + DPT head, prompt-conditioned
via CLIP ViT-L/14 text embeddings. We condition images on the SalEC
(e-commerce) prompt — the closest domain to ad creatives in AAM's training
mix — and video on the DHF1K free-viewing prompt.

Env contract (set by local_backend/app.py):
  AAM_REPO    — checkout of github.com/wz-zhao/Attend-to-Anything
  AAM_WEIGHTS — full-model checkpoint (includes backbone weights)

The CLIP text encoder is only needed once per prompt; embeddings are cached
next to the weights (aam_prompts.pt) so serving never loads CLIP.
"""

import os
import sys
import json

import numpy as np
import cv2

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_INPUT_SIZE = 448          # AAM trains/evals at 448x448
_VIDEO_CHUNK = 32          # frames per dynamic forward pass (= training snippet)

_STATE = {}                # lazy singleton: {"model", "device", "prompts"}

# Prompts copied verbatim from the AAM repo (prompts.py) so the cached
# embeddings stay valid even if the checkout moves.
_PROMPTS = {
    "image": (
        "Static e-commerce product image with packaging, brand logos, price tags "
        "and dense short text blocks; free-viewing eye-tracking dominated by text "
        "and logo-driven attention over retail and shopping items."
    ),
    "video": (
        "Dynamic free-viewing video across diverse scenes and camera motions, "
        "containing multiple moving objects and complex backgrounds; "
        "saliency-style eye-tracking with dispersed attention and weak center bias."
    ),
}


def _repo_dir():
    repo = os.environ.get("AAM_REPO")
    if not repo or not os.path.isdir(repo):
        raise RuntimeError(f"AAM_REPO not set or missing: {repo!r}")
    return repo


def _weights_path():
    w = os.environ.get("AAM_WEIGHTS")
    if not w or not os.path.exists(w):
        raise RuntimeError(f"AAM_WEIGHTS not set or missing: {w!r}")
    return w


def _prompt_embeds(device):
    """Load cached CLIP ViT-L/14 prompt embeddings, computing them once if needed."""
    import torch
    cache = os.path.join(os.path.dirname(_weights_path()), "aam_prompts.pt")
    if os.path.exists(cache):
        embeds = torch.load(cache, map_location="cpu")
    else:
        # One-time embedding build. open_clip with pretrained="openai" loads
        # the same ViT-L/14 text tower AAM used via the openai/CLIP package.
        import open_clip
        clip_model, _, _ = open_clip.create_model_and_transforms(
            "ViT-L-14-quickgelu", pretrained="openai")
        clip_model = clip_model.to(device).eval()
        tokenizer = open_clip.get_tokenizer("ViT-L-14")
        embeds = {}
        with torch.no_grad():
            for key, text in _PROMPTS.items():
                tokens = tokenizer([text]).to(device)
                embeds[key] = clip_model.encode_text(tokens).float().cpu()
        del clip_model
        torch.cuda.empty_cache()
        torch.save(embeds, cache)
        print(f"[aam] prompt embeddings cached to {cache}")
    return {k: v.to(device) for k, v in embeds.items()}


def _load():
    """Build the AAM model once and keep it resident."""
    if _STATE:
        return _STATE
    import torch
    repo = _repo_dir()
    if repo not in sys.path:
        sys.path.insert(0, repo)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Import the backbone constructor directly — the bundled dinov3 hubconf
    # imports detector/eval modules that aren't shipped in the AAM checkout.
    dinov3_root = os.path.join(repo, "dinov3")
    if dinov3_root not in sys.path:
        sys.path.insert(0, dinov3_root)
    from dinov3.hub.backbones import dinov3_vitl16
    backbone = dinov3_vitl16(pretrained=False, use_moe=False, text_dim=768)
    from dpt import DPT
    from LORA import apply_lora_dino_backbone
    model = DPT(nclass=1, backbone=backbone)
    # Same LoRA wrapping train.py applies before saving — without it the
    # checkpoint's attn.qkv.base/lora_A/lora_B keys don't match and the
    # backbone attention would silently stay random.
    apply_lora_dino_backbone(
        model, r=32, alpha=64, dropout=0.05,
        last_n_blocks=24, target=("attn.qkv", "attn.proj"))

    # weights_only=True: tensors only, no pickled code execution from the ckpt
    ckpt = torch.load(_weights_path(), map_location="cpu", weights_only=True)
    sd = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    sd = {(k[7:] if k.startswith("module.") else k): v for k, v in sd.items()}
    msg = model.load_state_dict(sd, strict=False)
    print(f"[aam] weights loaded (missing={len(msg.missing_keys)}, "
          f"unexpected={len(msg.unexpected_keys)})")
    if len(msg.missing_keys) > 50:
        raise RuntimeError(
            f"AAM checkpoint looks incompatible: {len(msg.missing_keys)} missing keys "
            f"(first: {msg.missing_keys[:3]})")
    model = model.to(device).eval()

    _STATE.update(model=model, device=device, prompts=_prompt_embeds(device))
    return _STATE


def _preprocess(bgr_frames):
    """BGR uint8 frames -> (N,3,448,448) ImageNet-normalized float tensor."""
    import torch
    batch = []
    for f in bgr_frames:
        rgb = cv2.cvtColor(cv2.resize(f, (_INPUT_SIZE, _INPUT_SIZE),
                                      interpolation=cv2.INTER_LINEAR),
                           cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        batch.append((rgb - _IMAGENET_MEAN) / _IMAGENET_STD)
    arr = np.stack(batch, axis=0).transpose(0, 3, 1, 2)
    return torch.from_numpy(arr)


def predict_image(bgr):
    """Saliency map in [0,1] at the input image's resolution."""
    import torch
    st = _load()
    x = _preprocess([bgr]).to(st["device"])
    with torch.no_grad():
        out, _ = st["model"](x, text_emb=st["prompts"]["image"], dynamic=False)
    m = out[0, 0].float().cpu().numpy()
    m = cv2.resize(m, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
    lo, hi = float(m.min()), float(m.max())
    return (m - lo) / (hi - lo) if hi - lo > 1e-8 else np.zeros_like(m)


def predict_video(bgr_frames):
    """Per-frame saliency maps (448x448 float arrays) for a list of BGR frames."""
    import torch
    st = _load()
    maps = []
    for i in range(0, len(bgr_frames), _VIDEO_CHUNK):
        chunk = bgr_frames[i:i + _VIDEO_CHUNK]
        x = _preprocess(chunk).to(st["device"])
        emb = st["prompts"]["video"].expand(len(chunk), -1)
        dynamic = len(chunk) > 1  # temporal module needs >=2 frames
        with torch.no_grad():
            out, _ = st["model"](x, text_emb=emb, dynamic=dynamic)
        maps.extend(out[:, 0].float().cpu().numpy())
    return maps


# ── Pipeline-facing entry points (mirror the legacy contracts) ──────────────

def compute_saliency_map_aam(image_path, output_path=None):
    """Same contract as analyze_image.compute_saliency_map (OpenCV version)."""
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    m = predict_image(img)
    if output_path:
        u8 = (m * 255).astype(np.uint8)
        heat = cv2.applyColorMap(u8, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(img, 0.5, heat, 0.5, 0)
        cv2.imwrite(output_path, overlay)
    return m, output_path


def analyze_saliency_aam(video_path, output_dir, keyframe_timestamps=None,
                         **_ignored):
    """Same return contract as saliency_module.analyze_saliency (TASED version)."""
    from saliency_module import (read_video_frames, write_overlay_video,
                                 overlay_heatmap, extract_gaze_region,
                                 _NumpyJSONEncoder)
    os.makedirs(output_dir, exist_ok=True)
    print(f"[aam] reading {video_path}...")
    frames, fps = read_video_frames(video_path)
    if not frames:
        return {"error": "No frames could be read"}
    print(f"[aam] {len(frames)} frames at {fps:.1f} fps")
    saliency_maps = predict_video(frames)
    gaze_per_frame = [extract_gaze_region(s, frames[0].shape) for s in saliency_maps]
    if keyframe_timestamps is None:
        keyframe_timestamps = list(np.arange(0, len(frames) / fps, 1.0))
    gaze_at_keyframes = []
    for ts in keyframe_timestamps:
        idx = min(int(ts * fps), len(gaze_per_frame) - 1)
        g = gaze_per_frame[idx].copy()
        g["timestamp"] = round(float(ts), 2)
        gaze_at_keyframes.append(g)
    overlay_path = os.path.join(output_dir, "saliency_overlay.mp4")
    write_overlay_video(frames, saliency_maps, fps, overlay_path)
    sample_dir = os.path.join(output_dir, "saliency_frames")
    os.makedirs(sample_dir, exist_ok=True)
    for ts in keyframe_timestamps:
        idx = min(int(ts * fps), len(frames) - 1)
        cv2.imwrite(os.path.join(sample_dir, f"saliency_t{ts:05.2f}s.png"),
                    overlay_heatmap(frames[idx], saliency_maps[idx]))
    summary = _summarize(gaze_at_keyframes)
    metadata = {
        "video_path": video_path, "fps": fps, "model": "AAM",
        "total_frames": len(frames), "duration_sec": len(frames) / fps,
        "overlay_video": overlay_path, "sample_frames_dir": sample_dir,
        "gaze_at_keyframes": gaze_at_keyframes,
        "diagnostic_summary": summary,
    }
    with open(os.path.join(output_dir, "saliency_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2, cls=_NumpyJSONEncoder)
    return metadata


def _summarize(gaze_at_keyframes):
    lines = ["Predicted gaze location per second (from AAM, a unified "
             "image/video attention model trained on human eye-tracking):"]
    zone_counts = {}
    for g in gaze_at_keyframes:
        zone_counts[g["zone"]] = zone_counts.get(g["zone"], 0) + 1
    total = sum(zone_counts.values())
    if total > 0:
        lines.append("\nGaze zone distribution:")
        for zone, count in sorted(zone_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {zone}: {100 * count / total:.0f}% of frames")
    lines.append("\nPer-second gaze trajectory:")
    for g in gaze_at_keyframes[:30]:
        lines.append(f"  t={g['timestamp']}s -> {g['zone']} "
                     f"(focus_strength={g['confidence_ratio']:.1f})")
    if len(gaze_at_keyframes) > 30:
        lines.append(f"  ... ({len(gaze_at_keyframes) - 30} more points)")
    if len(gaze_at_keyframes) > 1:
        zones = [g["zone"] for g in gaze_at_keyframes]
        transitions = sum(1 for i in range(1, len(zones)) if zones[i] != zones[i - 1])
        lines.append(f"\nGaze stability: {len(set(zones))} distinct zones, "
                     f"{transitions} zone transitions")
    return "\n".join(lines)
