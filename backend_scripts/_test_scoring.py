"""Local smoke/regression tests for the reworked scoring (no GPU, no Claude)."""
import sys, os
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import image_kpis as ik
import cognitive_kpis as ck


def _save(img, name):
    path = f"/tmp/{name}.png"
    cv2.imwrite(path, img)
    return path


def make_clean_premium():
    """Mostly empty cream canvas, one small dark product on a thirds point."""
    img = np.full((1000, 1000, 3), 235, np.uint8)
    cv2.rectangle(img, (640, 300), (760, 430), (40, 30, 30), -1)  # small subject
    return _save(img, "premium_kv")


def make_busy_banner():
    """Dense, high-contrast, lots of text lines — direct-response banner."""
    img = np.full((600, 1200, 3), 255, np.uint8)
    cv2.rectangle(img, (0, 0), (1200, 600), (20, 20, 200), -1)     # red field
    for i, y in enumerate(range(60, 520, 60)):                      # many text lines
        cv2.putText(img, "LIMITED TIME OFFER 50% OFF TODAY", (40, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
    return _save(img, "busy_banner")


print("=" * 70)
print("IMAGE SCORING")
print("=" * 70)

premium = make_clean_premium()
banner = make_busy_banner()

for path, fmt in [(premium, "KV"), (premium, "Banner"),
                  (banner, "KV"), (banner, "Banner")]:
    r = ik.compute_image_kpis(path, format_type=fmt)
    assert "error" not in r, r
    ks = r["kpis"]
    # invariants
    assert r["funnel_stage"] in ("upper", "mid", "lower")
    assert abs(sum(r["weights"].values()) - 1.0) < 1e-6, r["weights"]
    for k, v in ks.items():
        assert 0.0 <= v["score"] <= 10.0, (k, v["score"])
    name = os.path.basename(path)
    print(f"\n{name:14s} as {fmt:7s} funnel={r['funnel_stage']:5s} tier={r['product_tier']:11s} overall={r['overall']}")
    print(f"   ws={ks['white_space']['raw_value']:.2f}->{ks['white_space']['score']}  "
          f"text={ks['text_balance']['raw_value']:.2f}->{ks['text_balance']['score']}  "
          f"complexity={ks['complexity']['raw_value']:.3f}->{ks['complexity']['score']}  "
          f"contrast={ks['contrast']['score']}")

# Funnel sensitivity: same clean premium image should score whitespace HIGHER
# as a KV (wants 45-70%) than as a Banner (wants 22-45%) when ws is high.
kv = ik.compute_image_kpis(premium, format_type="KV")
bn = ik.compute_image_kpis(premium, format_type="Banner")
print(f"\nFunnel sensitivity (clean image): KV whitespace={kv['kpis']['white_space']['score']} "
      f"vs Banner whitespace={bn['kpis']['white_space']['score']}")

# Text load: busy banner should register MORE measured text area than clean KV.
t_busy = ik.estimate_text_area_ratio(cv2.imread(banner))
t_clean = ik.estimate_text_area_ratio(cv2.imread(premium))
print(f"Text-area estimate: busy_banner={t_busy:.2f}  clean_premium={t_clean:.2f}")
assert t_busy > t_clean, "text detector should see more text on the busy banner"

# Smoothness: white_space score should be continuous across the band edge.
img = cv2.imread(premium)
prev, maxjump = None, 0.0
for frac in np.linspace(0.0, 0.9, 19):
    # synthesize varying whitespace by blending noise in
    noise = (np.random.rand(*img.shape) * 255).astype(np.uint8)
    blended = cv2.addWeighted(img, 1 - frac, noise, frac, 0)
    cv2.imwrite("/tmp/_blend.png", blended)
    s = ik.white_space_ratio(blended, ws_band=(0.45, 0.70))["score"]
    if prev is not None:
        maxjump = max(maxjump, abs(s - prev))
    prev = s
print(f"White-space max step between adjacent samples: {maxjump:.1f} (smooth if < ~4)")

print("\n" + "=" * 70)
print("VIDEO SCORING")
print("=" * 70)


def make_video_report(*, attention, focus, distinct_zones, text_words,
                      interrupts, transitions, duration=20):
    """Synthesize a minimal report dict matching what the pipeline produces."""
    timeline = [{"t": float(t), "score": attention} for t in range(duration)]
    # inject `interrupts` big jumps
    for i in range(1, min(interrupts + 1, len(timeline))):
        timeline[i]["score"] = attention + (5 if i % 2 else -5)
    zones_pool = ["center", "top", "bottom", "left", "right"][:max(1, distinct_zones)]
    gaze = []
    for t in range(duration):
        # cycle through zones to create `transitions`
        zone = zones_pool[t % len(zones_pool)] if t < transitions else zones_pool[0]
        gaze.append({"timestamp": float(t), "zone": zone,
                     "confidence_ratio": focus})
    return {
        "perception": {"text_overlays": ("text " * text_words) if text_words else "no text"},
        "key_frames": {"metadata": {"duration_sec": duration, "score_timeline": timeline,
                                    "key_frames": []}},
        "audio": {"signals": {"energy_timeline": [], "first_3s_analysis": {}}},
        "saliency": {"gaze_at_keyframes": gaze},
    }


# Key test: a HIGH-attention, well-focused, low-text video should NOT be
# scored as high cognitive load (the old bug did exactly that).
high_quality = make_video_report(attention=9, focus=10, distinct_zones=1,
                                 text_words=0, interrupts=6, transitions=8)
cluttered = make_video_report(attention=5, focus=2, distinct_zones=5,
                              text_words=60, interrupts=2, transitions=18)

hq = ck.compute_cognitive_kpis(high_quality)
cl = ck.compute_cognitive_kpis(cluttered)

print(f"\nHigh-quality video: overall={hq['overall']}  cognitive_load={hq['kpis']['cognitive_load']['score']}")
print(f"Cluttered video:    overall={cl['overall']}  cognitive_load={cl['kpis']['cognitive_load']['score']}")
assert hq['kpis']['cognitive_load']['score'] > cl['kpis']['cognitive_load']['score'], \
    "high-quality focused video must have LOWER cognitive load (higher score) than cluttered one"

for rep, nm in [(hq, "hq"), (cl, "cl")]:
    assert abs(sum(rep["weights"].values()) - 1.0) < 1e-6
    for k, v in rep["kpis"].items():
        assert 0.0 <= v["score"] <= 10.0, (nm, k, v["score"])

# Smoothness of switching_cost across transition rates.
prev, maxjump = None, 0.0
for tr in range(0, 20):
    rep = make_video_report(attention=6, focus=6, distinct_zones=4,
                            text_words=0, interrupts=3, transitions=tr)
    s = ck.attention_switching_cost(rep)["score"]
    if prev is not None:
        maxjump = max(maxjump, abs(s - prev))
    prev = s
print(f"\nSwitching-cost max step between adjacent transition rates: {maxjump:.1f} (smooth if < ~4)")

print("\nALL ASSERTIONS PASSED ✅")
