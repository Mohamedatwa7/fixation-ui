"""Image KPIs with MAdVerse percentile benchmarking."""

import os, json, numpy as np, cv2

_BENCHMARK_CACHE = {}


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


def white_space_ratio(image_bgr, benchmark=None):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean = cv2.boxFilter(gray, -1, (11, 11))
    mean_sq = cv2.boxFilter(gray**2, -1, (11, 11))
    local_var = np.maximum(mean_sq - mean**2, 0)
    ws = float((local_var < 30).mean())
    if 0.30 <= ws <= 0.50: score = 10
    elif 0.20 <= ws < 0.30 or 0.50 < ws <= 0.65: score = 7
    elif ws < 0.20: score = max(2, 10 - (0.20 - ws) * 30)
    else: score = max(2, 10 - (ws - 0.65) * 20)
    percentile = None
    if benchmark and "white_space_ratio" in benchmark:
        percentile = lookup_percentile(ws, benchmark["white_space_ratio"])
    return {
        "score": round(min(10, max(0, score)), 1),
        "raw_value": round(ws, 3), "percentile": percentile,
        "label": "White space",
        "research_basis": "Bringhurst (2004); Williams (2014)",
        "methodology": f"White space ratio: {ws*100:.0f}% (optimal 30-50%)",
        "interpretation": "Optimal mid-range. Too low = cluttered, too high = sparse.",
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


def visual_complexity(image_bgr, benchmark=None):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    edge_density = float(edges.mean() / 255.0)
    if 0.04 <= edge_density <= 0.12: score = 10
    elif 0.02 <= edge_density < 0.04 or 0.12 < edge_density <= 0.20: score = 7
    elif edge_density < 0.02: score = max(2, edge_density * 200)
    else: score = max(2, 10 - (edge_density - 0.20) * 30)
    percentile = None
    if benchmark and "edge_density" in benchmark:
        percentile = lookup_percentile(edge_density, benchmark["edge_density"])
    return {
        "score": round(min(10, max(0, score)), 1),
        "raw_value": round(edge_density, 3), "percentile": percentile,
        "label": "Visual complexity",
        "research_basis": "Reinecke & Gajos (2014)",
        "methodology": f"Edge density: {edge_density*100:.1f}% (optimal 4-12%)",
        "interpretation": "Optimal mid-range. Too low = sparse, too high = overwhelming.",
    }


def text_image_balance(perception_text, image_bgr):
    text_desc = (perception_text or "").lower()
    word_count = len(text_desc.split())
    heavy = sum(["long" in text_desc, "paragraph" in text_desc,
                 "multiple lines" in text_desc, word_count > 80])
    if heavy >= 2: score = 4
    elif heavy == 1: score = 6
    elif "no text" in text_desc or "without text" in text_desc: score = 6
    elif "text" in text_desc or "caption" in text_desc: score = 8
    else: score = 7
    return {
        "score": round(score, 1), "raw_value": word_count, "percentile": None,
        "label": "Text-image balance",
        "research_basis": "Pieters & Wedel (2004)",
        "methodology": f"Text-overlay description: {word_count} words. Heavy-text signals: {heavy}",
        "interpretation": "High = image-driven with supportive text. Low = text-heavy.",
    }


def _default(label):
    return {"score": 5.0, "raw_value": None, "percentile": None, "label": label,
            "research_basis": "(unavailable)", "methodology": "Could not compute",
            "interpretation": ""}


def compute_image_kpis(image_path, perception=None, saliency_map=None,
                       benchmark_path=None):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        return {"error": f"Could not read image: {image_path}"}
    text_desc = (perception or {}).get("text_overlays", "") if perception else ""
    benchmark = load_benchmark(benchmark_path) if benchmark_path else None

    kpis = {
        "hierarchy": visual_hierarchy(image_bgr, saliency_map, benchmark),
        "composition": composition_balance(image_bgr, saliency_map, benchmark),
        "white_space": white_space_ratio(image_bgr, benchmark),
        "contrast": color_contrast(image_bgr, saliency_map, benchmark),
        "complexity": visual_complexity(image_bgr, benchmark),
        "text_balance": text_image_balance(text_desc, image_bgr),
    }
    weights = {"hierarchy": 0.25, "composition": 0.15, "white_space": 0.15,
               "contrast": 0.20, "complexity": 0.10, "text_balance": 0.15}
    overall = sum(kpis[k]["score"] * w for k, w in weights.items())

    return {
        "overall": round(overall, 1), "kpis": kpis, "weights": weights,
        "benchmark_used": benchmark_path if benchmark else None,
        "benchmark_n": benchmark.get("n_images") if isinstance(benchmark, dict) and "n_images" in benchmark else None,
    }
