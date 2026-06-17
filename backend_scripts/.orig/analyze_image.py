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
    "call_to_action": "Is there an explicit call to action (button, instruction, URL, hashtag)? Prominent and clear?",
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

Use the percentile data explicitly — e.g., "your hierarchy is in the 25th percentile of 50K ads" is much stronger than "your hierarchy could be better."

Be direct. If the design is strong, say so. Frame issues as hypotheses, not certainties.

Output strict JSON:
{
  "summary": "1-2 sentence overall assessment",
  "strengths": ["..."],
  "risks": [{"rank": 1, "issue": "...", "evidence": "...", "impact": "...", "suggested_fix": "...", "confidence": "high|medium|low"}],
  "hierarchy_analysis": "Where the eye lands vs. where it should",
  "brand_visibility": "How well brand element is positioned",
  "benchmark_context": "What the percentile rankings tell us",
  "diagnostic_caveats": "What this analysis cannot tell you"
}
"""


def run_image_diagnosis(perception, kpi_data, saliency_info, image_path,
                        title=None, description=None, format_type=None,
                        role_key="creative_director"):
    """Role-aware Claude diagnosis."""
    from anthropic import Anthropic
    sys.path.insert(0, "/content")
    from role_profiles import build_role_aware_system_prompt

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    client = Anthropic(api_key=api_key)

    perception_text = "\n\n".join(f"## {k.upper()}\n{v}" for k, v in perception.items())
    kpi_text = f"Overall design score: {kpi_data['overall']}/10\n"
    if kpi_data.get("benchmark_used"):
        kpi_text += f"Benchmark: MAdVerse ({kpi_data.get('benchmark_n', 'N')} reference ads)\n\n"
    for key, kpi in kpi_data["kpis"].items():
        pct_str = f", {kpi['percentile']}th percentile" if kpi.get("percentile") is not None else ""
        kpi_text += f"- {kpi['label']}: {kpi['score']}/10{pct_str}\n  Methodology: {kpi['methodology']}\n"

    saliency_text = saliency_info.get("summary", "(saliency unavailable)")
    system_prompt = build_role_aware_system_prompt(BASE_SYS_PROMPT, role_key, "image")

    user_message = (
        f"Image: {os.path.basename(image_path)}\nTitle: {title or '(none)'}\n"
        f"Format: {format_type or '(unspecified)'}\nBrief: {description or '(none)'}\n\n"
        f"PERCEPTION (Qwen2.5-VL):\n\n{perception_text}\n\n"
        f"DESIGN KPIs (with industry percentiles):\n\n{kpi_text}\n\n"
        f"SALIENCY:\n\n{saliency_text}\n\nProduce diagnostic JSON."
    )

    print(f"Sending to Claude (role: {role_key})...")
    response = client.messages.create(
        model="claude-opus-4-7", max_tokens=2500, system=system_prompt,
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
                  enable_localization=True):
    """
    Main pipeline. Now includes:
      - Localization assessment (Arabic + Urdu)
      - Role-aware diagnosis
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, "/content")
    from image_kpis import compute_image_kpis, text_image_balance

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
                                  benchmark_path=benchmark_path)

    print("\n--- STEP 3: Qwen perception ---")
    perception = run_image_perception(image_path, model_cache=model_cache)
    image_bgr = cv2.imread(image_path)
    kpi_data["kpis"]["text_balance"] = text_image_balance(
        perception.get("text_overlays", ""), image_bgr)
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
                                    role_key=role_key)

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
