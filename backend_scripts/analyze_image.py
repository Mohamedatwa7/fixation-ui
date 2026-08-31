"""Image Diagnostic: perception + saliency + KPIs (benchmark) + localization + role-aware Claude."""

import os, json, argparse, sys
from datetime import datetime
import cv2, numpy as np


IMAGE_PERCEPTION_QUESTIONS = {
    "subject": "What is the main subject of this image? Where is it positioned (center, top, bottom, left, right)?",
    "composition": "Describe the composition. Is it balanced? Does the focal point follow rule of thirds, dead-center, or off-balance?",
    "text_overlays": "Are there any text overlays, headlines, or graphics? What do they say, where are they placed, and are they readable?",
    "color_palette": "Describe the color palette. Are colors harmonious or contrasting? Does the subject stand out from the background?",
    "brand_elements": "Are there visible brand elements (logos, product shots, slogans)? Where are they placed? Prominent or hidden?",
    "emotional_tone": "What emotion or mood does this image convey? Is it consistent with the apparent intent?",
    "call_to_action": "Is there an explicit call to action (button, instruction, URL, hashtag)? If present, is it prominent and clear? If absent, just say so neutrally — absence is normal for awareness assets.",
}


def load_qwen_model(model_cache=None):
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
    model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
    print(f"Loading {model_id}...")
    kwargs = {"torch_dtype": torch.float16, "device_map": "auto"}
    if model_cache:
        kwargs["cache_dir"] = model_cache
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(model_id, **kwargs)
    processor = AutoProcessor.from_pretrained(model_id, cache_dir=model_cache)
    print("Qwen loaded.")
    return model, processor


def query_qwen_on_image(model, processor, image_path, question, max_new_tokens=300):
    import torch
    from qwen_vl_utils import process_vision_info
    messages = [{"role": "user", "content": [
        {"type": "image", "image": image_path},
        {"type": "text", "text": question}]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                       padding=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
    trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(trimmed, skip_special_tokens=True,
                                  clean_up_tokenization_spaces=False)[0].strip()


def run_image_perception(image_path, model_cache=None):
    import torch
    model, processor = load_qwen_model(model_cache)
    print("Running perception...")
    perception = {}
    for key, q in IMAGE_PERCEPTION_QUESTIONS.items():
        print(f"  -> {key}")
        try:
            perception[key] = query_qwen_on_image(model, processor, image_path, q)
        except Exception as e:
            perception[key] = f"[error: {e}]"
    del model, processor
    torch.cuda.empty_cache()
    return perception


def compute_saliency_map(image_path, output_path=None):
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    sal = cv2.saliency.StaticSaliencyFineGrained_create()
    ok, m = sal.computeSaliency(img)
    if not ok:
        return None, None
    if output_path:
        H, W = img.shape[:2]
        u8 = (m * 255).astype(np.uint8)
        heat = cv2.applyColorMap(u8, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(img, 0.5, heat, 0.5, 0)
        cv2.imwrite(output_path, overlay)
    return m, output_path


BASE_SYS_PROMPT = """You are a senior creative director reviewing a static creative (KV, OOH, banner, print ad).

You are given:
1. Perception report from Qwen2.5-VL
2. Design KPI scores grounded in graphic design research
3. Industry-benchmark percentile rankings (vs. MAdVerse, 50K real ads from WACV 2024)
4. Saliency analysis

Job:
1. Top 3 specific design risks ranked by impact.
2. Each risk cites perception/KPI/percentile/saliency evidence.
3. Concrete testable fix.
4. A "revision_brief": a complete remake plan a designer could execute without
   follow-up questions — specific to THIS creative (name its actual elements,
   zones, and copy), never generic advice.

SAMSUNG BRAND CONSTRAINTS FOR ALL RECOMMENDATIONS
This deployment analyzes Samsung creative. Every suggested_fix and every
revision_brief section must be executable within the Samsung Brand Creative
Playbook (Global Brand Center, Apr 2026):
- Essence: the Confident Explorer (Open, Bold, Authentic) delivering REFINED
  WIT — clarity plus surprise, a gentle wink, rooted in real life. Never
  loud/obnoxious, silly/cutesy, busy/dense, staged/faked, or mechanical/cold.
- Copy you propose must use the brand voice techniques — personify the tech,
  upend expectations, "not just this, but also that", confident POV, "Detail.
  Detail. Emotion.", play up contrast, write to a friend, find the upside,
  find the tangible benefit. One voice attribute per short line. Calibrate
  against real Samsung headline craft: "Don't move a muscle." / "See better
  than the ref." / "Ready. Set. Flip."
- Type: SamsungSharpSans only (Head above 18pt, Body below); clear size/weight
  hierarchy; type color blue, white, or black for most occasions.
- Color: blue must appear in the composition — Confident Blue #020DCB for
  digital, Samsung Blue #1428A0 for print/corporate — with white/black
  dominant and creative colors as sparing accents.
- Imagery: imagination rooted in real moments — no surreal devices; Open =
  negative space and curiosity, Bold = dynamic angles and striking contrast,
  Authentic = natural light and unposed moments.
- Name the specific technique, color, or type treatment when you recommend it.
  If a high-engagement tactic exists that the brand cannot ship, propose the
  nearest refined-wit equivalent instead.

JUDGE AGAINST THE ASSET'S FUNNEL STAGE — NOT A UNIVERSAL CHECKLIST.
Every stage has its own success criteria; the absence of another stage's devices is not a defect:
- Upper funnel (awareness): judged on attention, emotion, distinctiveness, and brand attribution. A missing CTA, offer, price, or urgency cue is CORRECT here — never list it as a risk or fix for an upper-funnel asset. Deliberate minimalism, teaser withholding, and generous whitespace are stage-appropriate strengths.
- Mid funnel (consideration): judged on value comprehension and feature clarity. A soft or passive CTA is acceptable; a hard offer is not required.
- Lower funnel (conversion): judged on offer strength, CTA prominence, urgency, and trust signals. Here a weak or missing CTA IS a top-rank risk. Conversely, do not flag density or commercial tone that serves direct response.
Before writing each risk, check it against the stage: if the "fix" would push the asset toward a different funnel stage, discard it and find a risk within the asset's own job.

RANK RISKS BY EXPECTED SCORE IMPACT, NOT BY VISUAL SEVERITY.
When the user message includes ENGAGEMENT SCORE WEIGHTS, they are the exact weights that produce this asset's Engagement Potential score at its funnel stage, plus organic-engagement weights refit against realized in-feed engagement (a NEGATIVE organic weight means polishing that dimension anti-correlates with organic engagement). Use them:
- Estimate each candidate risk's impact as (weight of the KPI its fix would move) x (realistic points of movement), and rank risks by that product.
- Name the KPI each risk targets in a "score_lever" field, e.g. "emotional_pull (weight 0.26)".
- On upper-funnel assets, most of the score sits in concept-level judged KPIs (emotional pull, distinctiveness, talkability, brand strength). At least one of your top-2 risks must target a concept lever, with a suggested_fix executable as a creative revision — a nameable emotional idea, a distinctive visual device, a share/comment hook — not only execution polish (contrast, alignment, watermark cleanup).
- When a fix is pure attention/clarity polish and that KPI's organic weight is negative, state the tradeoff in "impact" and rank it accordingly; it must never be risk #1 on an upper-funnel asset.

Use the percentile data explicitly — e.g., "your hierarchy is in the 25th percentile of 50K ads" is much stronger than "your hierarchy could be better."

HONOR THE ADVERTISER CONTEXT. When the user message includes an ADVERTISER
CONTEXT block (title, format, brief), treat it as ground truth about the
campaign's audience, market, objective, and constraints. Judge the creative
against THAT job — not a generic one — reference the context explicitly in
your summary and risks where relevant, and tailor every suggested_fix and
revision_brief section to it. If the context contradicts what the creative
shows, name that mismatch as a risk.

Be direct. If the design is strong, say so. Frame issues as hypotheses, not certainties.

Output strict JSON:
{
  "summary": "1-2 sentence overall assessment",
  "strengths": ["..."],
  "risks": [{"rank": 1, "issue": "...", "evidence": "...", "impact": "...", "suggested_fix": "...", "score_lever": "kpi_name (weight 0.00)", "confidence": "high|medium|low"}],
  "hierarchy_analysis": "Where the eye lands vs. where it should",
  "brand_visibility": "How well brand element is positioned",
  "benchmark_context": "What the percentile rankings tell us",
  "diagnostic_caveats": "What this analysis cannot tell you",
  "revision_brief": {
    "objective": "The single engagement problem this revision must solve, in one sentence",
    "focal_hierarchy": "What the eye should land on first, second, third — and the exact layout/scale/contrast changes to achieve it",
    "headline_copy": "The rewritten headline and supporting copy, in brand voice, naming the technique used",
    "color_type": "Palette and typography changes: which brand colors where, type faces/weights/sizes for each text level",
    "offer_cta": "Offer and CTA treatment appropriate to this funnel stage (for upper funnel: the closing brand moment instead — never push a stage change)",
    "imagery": "Product and imagery changes: crop, angle, casting, styling, background",
    "measurement": "Which KPI(s) the revision should move and how to A/B verify it"
  }
}
"""


def _score_weight_text(stage, score_weights):
    """Render the engagement-score weight tables for the diagnosis prompt so the
    critic can rank risks by expected score impact (weight x movement)."""
    if not score_weights:
        return ""
    funnel_tables = score_weights.get("funnel") or {}
    fw = funnel_tables.get(stage) or funnel_tables.get("mid") or {}
    lines = [f"ENGAGEMENT SCORE WEIGHTS (funnel stage: {stage}) — the final score "
             "is the weighted sum of these five KPIs; a fix that cannot move one "
             "of them cannot move the score:"]
    lines += [f"- {k}: {w:.2f}" for k, w in fw.items()]
    ow = score_weights.get("organic") or {}
    if ow:
        lines.append("ORGANIC ENGAGEMENT WEIGHTS (refit against realized in-feed "
                     "engagement; NEGATIVE weight = polishing this dimension "
                     "anti-correlates with organic engagement):")
        lines += [f"- {k}: {w:+.3f}" for k, w in ow.items()]
    return "\n".join(lines)


def run_image_diagnosis(perception, kpi_data, saliency_info, image_path,
                        title=None, description=None, format_type=None,
                        role_key="creative_director",
                        funnel_hint=None, score_weights=None):
    """Role-aware Claude diagnosis."""
    from anthropic import Anthropic
    sys.path.insert(0, "/content")
    from role_profiles import build_role_aware_system_prompt

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    client = Anthropic(api_key=api_key)

    perception_text = "\n\n".join(f"## {k.upper()}\n{v}" for k, v in perception.items())
    # The judge's funnel call (when available) wins over the CV-inferred stage so
    # the critique is ranked against the same weights that produce the score.
    stage = funnel_hint or kpi_data.get("funnel_stage") or "mid"
    kpi_text = ""
    if stage:
        kpi_text += (f"Inferred funnel stage: {stage} "
                     f"(product tier: {kpi_data.get('product_tier', 'n/a')}). "
                     f"Interpret every score relative to this — e.g. generous whitespace "
                     f"and low text are correct for upper funnel, denser layouts are correct "
                     f"for lower-funnel direct response.\n")
    kpi_text += f"Overall design score: {kpi_data['overall']}/10\n"
    if kpi_data.get("benchmark_used"):
        kpi_text += f"Benchmark: MAdVerse ({kpi_data.get('benchmark_n', 'N')} reference ads)\n\n"
    for key, kpi in kpi_data["kpis"].items():
        pct_str = f", {kpi['percentile']}th percentile" if kpi.get("percentile") is not None else ""
        kpi_text += f"- {kpi['label']}: {kpi['score']}/10{pct_str}\n  Methodology: {kpi['methodology']}\n"

    saliency_text = saliency_info.get("summary", "(saliency unavailable)")
    system_prompt = build_role_aware_system_prompt(BASE_SYS_PROMPT, role_key, "image")

    weights_text = _score_weight_text(stage, score_weights)
    context_block = ""
    if title or description or format_type:
        context_block = (
            "ADVERTISER CONTEXT (ground truth — honor in every judgment and recommendation):\n"
            f"Title: {title or '(none)'}\n"
            f"Format: {format_type or '(unspecified)'}\n"
            f"Brief: {description or '(none)'}\n\n"
        )
    user_message = (
        f"Image: {os.path.basename(image_path)}\n\n{context_block}"
        f"PERCEPTION (Qwen2.5-VL):\n\n{perception_text}\n\n"
        f"DESIGN KPIs (with industry percentiles):\n\n{kpi_text}\n\n"
        + (f"{weights_text}\n\n" if weights_text else "")
        + f"SALIENCY:\n\n{saliency_text}\n\nProduce diagnostic JSON."
    )

    print(f"Sending to Claude (role: {role_key})...")
    response = client.messages.create(
        model="claude-opus-4-7", max_tokens=5000,
        # constant per role -> prompt-cache it; hits cost ~10% of the input
        system=[{"type": "text", "text": system_prompt,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}])
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw_response": raw, "_parse_error": True}


def analyze_image(image_path, title=None, description=None, format_type=None,
                  output_path="image_report.json", model_cache=None,
                  benchmark_path=None, role_key="creative_director",
                  enable_localization=True, lite=False,
                  funnel_hint=None, score_weights=None):
    """
    Main pipeline. Now includes:
      - Localization assessment (Arabic + Urdu)
      - Role-aware diagnosis
    lite=True skips Qwen perception, localization, and the Claude diagnosis —
    saliency + CV KPIs only. Used by calibration/eval scoring where only the
    engagement score is needed; cuts the per-image LLM cost to the judge calls
    alone and removes the slowest pipeline steps.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, "/content")
    from image_kpis import compute_image_kpis, text_image_balance, get_format_profile

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    output_dir = output_path.replace(".json", "_outputs")
    os.makedirs(output_dir, exist_ok=True)

    print("\n--- STEP 1: Saliency ---")
    overlay_path = os.path.join(output_dir, "saliency_overlay.png")
    sal_map, _ = compute_saliency_map(image_path, overlay_path)
    saliency_info = {"overlay_path": overlay_path}
    if sal_map is not None:
        peak, mean = float(sal_map.max()), float(sal_map.mean())
        saliency_info["summary"] = f"Peak: {peak:.3f}, mean: {mean:.3f}, ratio: {peak/(mean+1e-8):.1f}"

    print("\n--- STEP 2: Design KPIs ---")
    kpi_data = compute_image_kpis(image_path, saliency_map=sal_map,
                                  benchmark_path=benchmark_path,
                                  format_type=format_type)

    if lite:
        print("\n--- lite mode: skipping perception / localization / diagnosis ---")
        perception = {}
        overall = sum(kpi_data["kpis"][k]["score"] * w
                      for k, w in kpi_data["weights"].items())
        kpi_data["overall"] = round(overall, 1)
        localization = None
        diagnosis = {"summary": "(lite mode: diagnosis skipped)", "risks": [],
                     "strengths": []}
    else:
        print("\n--- STEP 3: Qwen perception ---")
        perception = run_image_perception(image_path, model_cache=model_cache)
        image_bgr = cv2.imread(image_path)
        # Refine text-balance now that we have the VLM's read of on-screen text.
        # The magnitude stays pixel-based (estimate_text_area_ratio); perception is
        # only a presence/absence tie-breaker inside text_image_balance.
        profile = get_format_profile(format_type)
        kpi_data["kpis"]["text_balance"] = text_image_balance(
            image_bgr, perception.get("text_overlays", ""), text_max=profile["text_max"])
        overall = sum(kpi_data["kpis"][k]["score"] * w
                      for k, w in kpi_data["weights"].items())
        kpi_data["overall"] = round(overall, 1)

        # === NEW: Localization assessment ===
        localization = None
        if enable_localization:
            print("\n--- STEP 4a: Localization analysis ---")
            try:
                from localization import assess_localization
                localization = assess_localization(
                    perception.get("text_overlays", ""), format_type)
                risk = localization.get("market_fit_risk", "unknown")
                print(f"  Market-fit risk: {risk}")
            except Exception as e:
                print(f"  Localization failed: {e}")
                localization = {"error": str(e)}

        print(f"\n--- STEP 4b: Role-aware synthesis (role: {role_key}) ---")
        diagnosis = run_image_diagnosis(perception, kpi_data, saliency_info,
                                        image_path, title, description, format_type,
                                        role_key=role_key,
                                        funnel_hint=funnel_hint,
                                        score_weights=score_weights)

    report = {
        "image_path": image_path, "title": title, "description": description,
        "format_type": format_type, "role_key": role_key,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model_stack": "Qwen2.5-VL + OpenCV saliency + design KPIs + MAdVerse + localization + role-aware Claude",
        "benchmark_path": benchmark_path,
        "perception": perception, "kpis": kpi_data,
        "saliency": saliency_info, "diagnosis": diagnosis,
        "localization": localization,
    }

    class NumpyEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, np.floating): return float(o)
            if isinstance(o, np.integer): return int(o)
            if isinstance(o, np.ndarray): return o.tolist()
            return super().default(o)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, cls=NumpyEncoder)
    print(f"\n✅ Saved to {output_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--format", default=None)
    parser.add_argument("--output", default="image_report.json")
    parser.add_argument("--model-cache", default="/content/drive/MyDrive/lmm_evqa/qwen_cache")
    parser.add_argument("--benchmark", default=None)
    parser.add_argument("--role", default="creative_director",
                        choices=["creative_director", "marketer", "strategist", "executive"])
    parser.add_argument("--no-localization", action="store_true")
    args = parser.parse_args()
    analyze_image(args.image_path, args.title, args.description, args.format,
                  args.output, args.model_cache, args.benchmark,
                  role_key=args.role,
                  enable_localization=not args.no_localization)
