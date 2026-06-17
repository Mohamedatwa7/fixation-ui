"""Image KPIs with MAdVerse percentile benchmarking.

Scores are now interpreted relative to the asset's funnel stage (upper /
mid / lower), inferred from the creative format. The same whitespace ratio
or text load is judged differently for an awareness KV than for a
direct-response banner — this mirrors how a creative strategist reads an
asset rather than applying one fixed "optimal" band to everything.
"""

import os, json, numpy as np, cv2

_BENCHMARK_CACHE = {}


# ---------------------------------------------------------------------------
# Funnel / format profiles
# ---------------------------------------------------------------------------
# Each profile sets the optimal whitespace band, the tolerated text-area
# ratio, and the KPI weighting for that funnel stage. Upper-funnel awareness
# assets reward breathing room and a strong thumb-stop; lower-funnel direct
# response tolerates denser layouts and weights text/offer legibility higher.

FORMAT_PROFILES = {
    # format    funnel    whitespace band   max text area   tier hint
    "KV":     {"funnel": "upper", "ws_band": (0.45, 0.70), "text_max": 0.20, "tier": "premium"},
    "OOH":    {"funnel": "upper", "ws_band": (0.50, 0.75), "text_max": 0.15, "tier": "mass-market"},
    "Print":  {"funnel": "mid",   "ws_band": (0.35, 0.60), "text_max": 0.30, "tier": "premium"},
    "Social": {"funnel": "mid",   "ws_band": (0.30, 0.55), "text_max": 0.30, "tier": "mid-market"},
    "Banner": {"funnel": "lower", "ws_band": (0.22, 0.45), "text_max": 0.45, "tier": "mass-market"},
}

_DEFAULT_PROFILE = {"funnel": "mid", "ws_band": (0.30, 0.55), "text_max": 0.30, "tier": "mid-market"}

# Per-funnel KPI weights (each row sums to 1.0). Upper funnel leans on
# thumb-stop contrast, whitespace, hierarchy and composition; lower funnel
# shifts weight onto text/offer legibility and hierarchy.
WEIGHTS_BY_FUNNEL = {
    "upper": {"hierarchy": 0.22, "composition": 0.16, "white_space": 0.18,
              "contrast": 0.22, "complexity": 0.10, "text_balance": 0.12},
    "mid":   {"hierarchy": 0.22, "composition": 0.15, "white_space": 0.13,
              "contrast": 0.18, "complexity": 0.10, "text_balance": 0.22},
    "lower": {"hierarchy": 0.20, "composition": 0.12, "white_space": 0.10,
              "contrast": 0.16, "complexity": 0.12, "text_balance": 0.30},
}


def get_format_profile(format_type):
    """Map a creative format string to its funnel/whitespace/text profile."""
    if not format_type:
        return _DEFAULT_PROFILE
    key = str(format_type).strip()
    # Case-insensitive match against known formats.
    for k, v in FORMAT_PROFILES.items():
        if k.lower() == key.lower():
            return v
    return _DEFAULT_PROFILE


def _band_score(value, lo, hi, below_falloff, above_falloff):
    """Smooth 'plateau' score: 10 inside [lo, hi], linear decay outside.

    Replaces hard step bins so two near-identical assets don't jump several
    points across a threshold. `*_falloff` is the distance over which the
    score decays from 10 to 0 on each side of the optimal band.
    """
    if value < lo:
        return max(0.0, 10.0 - (lo - value) / max(below_falloff, 1e-6) * 10.0)
    if value > hi:
        return max(0.0, 10.0 - (value - hi) / max(above_falloff, 1e-6) * 10.0)
    return 10.0


def load_benchmark(path):
    if path in _BENCHMARK_CACHE:
        return _BENCHMARK_CACHE[path]
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    _BENCHMARK_CACHE[path] = data
    return data


def lookup_percentile(value, metric_table, lower_is_better=False):
    if value is None or metric_table is None:
        return None
    pcts = metric_table["percentiles"]
    keys_sorted = sorted([int(k) for k in pcts.keys()])
    pct = 100
    for p in keys_sorted:
        if value <= pcts[str(p)]:
            pct = p
            break
    if lower_is_better:
        pct = 100 - pct
    return pct


def _compute_saliency(image_bgr):
    try:
        sal = cv2.saliency.StaticSaliencySpectralResidual_create()
        ok, m = sal.computeSaliency(image_bgr)
        return m.astype(np.float32) if ok else None
    except Exception:
        return None


def estimate_text_area_ratio(image_bgr):
    """Estimate the fraction of the asset covered by text, from pixels.

    Uses a classic morphological text-region heuristic: gradient -> binarize
    -> close horizontally so glyphs merge into line/word blobs -> keep
    contours whose size and aspect ratio look like text. This measures the
    actual on-canvas text load instead of the verbosity of a VLM's prose
    description (the previous approach, which rewarded terse captions and
    punished chatty ones regardless of what was on screen).

    Returns a float in [0, 1]; falls back to a conservative estimate on error.
    """
    try:
        H, W = image_bgr.shape[:2]
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        # Close horizontally to connect characters into text lines.
        kernel_w = max(9, W // 40)
        closed = cv2.morphologyEx(
            bw, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 3)))
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        text_area = 0
        img_area = float(H * W)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if h < 8 or h > H * 0.4:           # too thin to read / too tall to be text
                continue
            ar = w / float(h + 1e-6)
            if ar < 1.2:                        # text lines are wider than tall
                continue
            fill = cv2.contourArea(c) / float(w * h + 1e-6)
            if fill < 0.2:                      # sparse blob, likely texture
                continue
            text_area += w * h
        return float(min(1.0, text_area / img_area))
    except Exception:
        return 0.15


def visual_hierarchy(image_bgr, saliency_map=None, benchmark=None):
    sal = saliency_map if saliency_map is not None else _compute_saliency(image_bgr)
    if sal is None:
        return _default("Visual hierarchy")
    peak, mean = float(sal.max()), float(sal.mean())
    ratio = peak / (mean + 1e-8)
    # Continuous: flat field (ratio≈1) → ~0, one dominant focal point (ratio≥6) → 10.
    score = round(min(10.0, max(0.0, (ratio - 1.0) * 2.0)), 1)
    percentile = None
    if benchmark and "hierarchy_ratio" in benchmark:
        percentile = lookup_percentile(ratio, benchmark["hierarchy_ratio"])
    return {
        "score": float(score), "raw_value": round(ratio, 2),
        "percentile": percentile, "label": "Visual hierarchy",
        "research_basis": "Tufte (1990); Lidwell et al. (2010)",
        "methodology": f"Saliency peak-to-mean ratio: {ratio:.1f}",
        "interpretation": "High = one clear focal point. Low = competing elements.",
    }


def composition_balance(image_bgr, saliency_map=None, benchmark=None):
    H, W = image_bgr.shape[:2]
    sal = saliency_map if saliency_map is not None else _compute_saliency(image_bgr)
    if sal is None:
        return _default("Composition balance")
    sal = cv2.resize(sal.astype(np.float32), (W, H))
    sal_pos = np.maximum(sal, 0)
    total = sal_pos.sum()
    if total < 1e-8:
        return _default("Composition balance")
    ys, xs = np.indices(sal.shape)
    cx = float((xs * sal_pos).sum() / total)
    cy = float((ys * sal_pos).sum() / total)
    intersections = [(W/3, H/3), (2*W/3, H/3), (W/3, 2*H/3), (2*W/3, 2*H/3)]
    min_dist = min(np.hypot(cx - ix, cy - iy) for ix, iy in intersections)
    normalized_dist = min_dist / np.hypot(W, H)
    score = max(0, min(10, 10 * (1 - normalized_dist * 4)))
    percentile = None
    if benchmark and "composition_dist" in benchmark:
        percentile = lookup_percentile(normalized_dist, benchmark["composition_dist"],
                                       lower_is_better=True)
    return {
        "score": round(score, 1), "raw_value": round(normalized_dist, 3),
        "percentile": percentile, "label": "Composition balance",
        "research_basis": "Smith (1797); Arnheim (1974)",
        "methodology": f"Centroid distance to thirds: {min_dist:.0f}px (norm {normalized_dist:.2f})",
        "interpretation": "High = subject on thirds grid. Low = dead-center or off-balance.",
    }


def white_space_ratio(image_bgr, benchmark=None, ws_band=(0.30, 0.50)):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean = cv2.boxFilter(gray, -1, (11, 11))
    mean_sq = cv2.boxFilter(gray**2, -1, (11, 11))
    local_var = np.maximum(mean_sq - mean**2, 0)
    ws = float((local_var < 30).mean())
    lo, hi = ws_band
    # Smooth decay outside the funnel-appropriate band (was a 4-step ladder).
    score = _band_score(ws, lo, hi, below_falloff=0.30, above_falloff=0.35)
    percentile = None
    if benchmark and "white_space_ratio" in benchmark:
        percentile = lookup_percentile(ws, benchmark["white_space_ratio"])
    return {
        "score": round(min(10, max(0, score)), 1),
        "raw_value": round(ws, 3), "percentile": percentile,
        "label": "White space",
        "research_basis": "Bringhurst (2004); Williams (2014)",
        "methodology": f"White space ratio: {ws*100:.0f}% (optimal for format: {lo*100:.0f}-{hi*100:.0f}%)",
        "interpretation": "Optimal band is funnel-relative. Too low = cluttered, too high = sparse.",
    }


def color_contrast(image_bgr, saliency_map=None, benchmark=None):
    H, W = image_bgr.shape[:2]
    sal = saliency_map if saliency_map is not None else _compute_saliency(image_bgr)
    if sal is None:
        return _default("Color contrast")
    sal = cv2.resize(sal.astype(np.float32), (W, H))
    sm = sal / (sal.max() + 1e-8)

    # Saliency-weighted subject vs inverse-weighted background, sharpened (^2) so
    # a small-but-salient subject's colour isn't averaged away by a large
    # background (which a hard top-percentile mask does to small subjects).
    w_sub = sm ** 2
    w_bg = (1.0 - sm) ** 2
    if w_sub.sum() < 1e-6 or w_bg.sum() < 1e-6:
        return _default("Color contrast")

    # Perceptual subject-vs-background distinctiveness in CIELAB (CIE76 ΔE).
    # Captures BOTH lightness and colour/chroma contrast — e.g. a saturated red
    # subject on a green field, which a pure luminance ratio scores as "low".
    # cv2 LAB is 8-bit scaled; convert back to real L*a*b* units first.
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0   # L: 0..100
    lab[..., 1] -= 128.0           # a: -128..127
    lab[..., 2] -= 128.0           # b: -128..127
    subj = (lab * w_sub[..., None]).sum(axis=(0, 1)) / w_sub.sum()
    bg = (lab * w_bg[..., None]).sum(axis=(0, 1)) / w_bg.sum()
    delta_e = float(np.sqrt(((subj - bg) ** 2).sum()))

    # Continuous calibration: just-noticeable (ΔE≈2-3) → ~0, strong pop
    # (ΔE≈40+) → ~9-10. Spans the full range instead of snapping to bins.
    score = round(min(10.0, max(0.0, 10.0 * (1.0 - np.exp(-delta_e / 18.0)))), 1)

    # WCAG-style luminance ratio kept for the methodology readout only.
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sl = float((gray * w_sub).sum() / w_sub.sum())
    bl = float((gray * w_bg).sum() / w_bg.sum())
    lum = (max(sl, bl) / 255.0 + 0.05) / (min(sl, bl) / 255.0 + 0.05)

    percentile = None
    if benchmark and "contrast_ratio" in benchmark:
        percentile = lookup_percentile(lum, benchmark["contrast_ratio"])
    return {
        "score": score, "raw_value": round(delta_e, 1),
        "percentile": percentile, "label": "Color contrast",
        "research_basis": "Itten (1961); CIE76 ΔE; WCAG 2.1",
        "methodology": f"Subject vs background CIELAB ΔE = {delta_e:.0f} (luminance {lum:.1f}:1)",
        "interpretation": "High = subject pops in colour and lightness. Low = blends in.",
    }


def visual_complexity(image_bgr, benchmark=None, funnel="mid"):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    edge_density = float(edges.mean() / 255.0)
    # Lower-funnel direct response tolerates a denser layout; widen the upper
    # edge of the optimal band there. Smooth decay (was a 4-step ladder).
    hi = 0.16 if funnel == "lower" else 0.12
    score = _band_score(edge_density, 0.04, hi, below_falloff=0.06, above_falloff=0.16)
    percentile = None
    if benchmark and "edge_density" in benchmark:
        percentile = lookup_percentile(edge_density, benchmark["edge_density"])
    return {
        "score": round(min(10, max(0, score)), 1),
        "raw_value": round(edge_density, 3), "percentile": percentile,
        "label": "Visual complexity",
        "research_basis": "Reinecke & Gajos (2014)",
        "methodology": f"Edge density: {edge_density*100:.1f}% (optimal 4-{hi*100:.0f}%)",
        "interpretation": "Optimal mid-range. Too low = sparse, too high = overwhelming.",
    }


def text_image_balance(image_bgr, perception_text=None, text_max=0.30):
    """Score text load against the funnel-appropriate maximum.

    Primary signal is the measured on-canvas text-area ratio. The VLM
    perception text is only used as a tie-breaker to confirm presence/absence
    of text, never as the magnitude (its word count reflects how verbose the
    model was, not how much text is on the asset).
    """
    text_ratio = estimate_text_area_ratio(image_bgr)

    desc = (perception_text or "").lower()
    says_no_text = ("no text" in desc or "without text" in desc or "no visible text" in desc)
    if says_no_text and text_ratio < 0.05:
        text_ratio = 0.0

    # Full marks at/under the format's tolerated text area; smooth decay above.
    score = _band_score(text_ratio, 0.0, text_max, below_falloff=1.0, above_falloff=0.30)
    return {
        "score": round(min(10, max(0, score)), 1),
        "raw_value": round(text_ratio, 3), "percentile": None,
        "label": "Text-image balance",
        "research_basis": "Pieters & Wedel (2004)",
        "methodology": f"Measured text area: {text_ratio*100:.0f}% of canvas (format tolerates ≤{text_max*100:.0f}%)",
        "interpretation": "High = image-driven with supportive text. Low = text-heavy for the format.",
    }


def _default(label):
    return {"score": 5.0, "raw_value": None, "percentile": None, "label": label,
            "research_basis": "(unavailable)", "methodology": "Could not compute",
            "interpretation": ""}


def compute_image_kpis(image_path, perception=None, saliency_map=None,
                       benchmark_path=None, format_type=None):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        return {"error": f"Could not read image: {image_path}"}
    text_desc = (perception or {}).get("text_overlays", "") if perception else ""
    benchmark = load_benchmark(benchmark_path) if benchmark_path else None

    profile = get_format_profile(format_type)
    funnel = profile["funnel"]

    kpis = {
        "hierarchy": visual_hierarchy(image_bgr, saliency_map, benchmark),
        "composition": composition_balance(image_bgr, saliency_map, benchmark),
        "white_space": white_space_ratio(image_bgr, benchmark, ws_band=profile["ws_band"]),
        "contrast": color_contrast(image_bgr, saliency_map, benchmark),
        "complexity": visual_complexity(image_bgr, benchmark, funnel=funnel),
        "text_balance": text_image_balance(image_bgr, text_desc, text_max=profile["text_max"]),
    }
    weights = WEIGHTS_BY_FUNNEL.get(funnel, WEIGHTS_BY_FUNNEL["mid"])
    overall = sum(kpis[k]["score"] * w for k, w in weights.items())

    return {
        "overall": round(overall, 1), "kpis": kpis, "weights": weights,
        "funnel_stage": funnel, "product_tier": profile["tier"],
        "format_type": format_type,
        "benchmark_used": benchmark_path if benchmark else None,
        "benchmark_n": benchmark.get("n_images") if isinstance(benchmark, dict) and "n_images" in benchmark else None,
    }
