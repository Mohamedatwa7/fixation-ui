"""Video Engagement Diagnostic v5: Qwen + Key-frames + Audio + Saliency + Claude."""

import argparse, json, os, sys
import numpy as np


class _NumpyJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)
from datetime import datetime

PERCEPTION_QUESTIONS = {
    "hook": "Describe what happens in the first 3 seconds of this video in detail. What is the viewer seeing? Is there a clear focal point? Is there motion, a visual surprise, or strong contrast?",
    "subject": "What is the main subject of this video? Where is it positioned on screen (center, top, bottom, left, right)? Is it consistently visible throughout, or does the subject change?",
    "pacing": "Describe the pacing. Are there frequent cuts and scene changes, or is it mostly one continuous shot? Does the visual energy build, stay flat, or drop?",
    "text_overlays": "Are there any text overlays, captions, or graphics on screen? If yes, what do they say and where are they placed? Are they readable?",
    "composition": "Describe the framing. Is this a vertical (9:16), square, or horizontal video? Is the main subject framed well, or are important elements near the edges where mobile UI overlays would cover them?",
    "ending": "Describe the last 2 seconds of the video. Is there a clear ending, a call to action, or does it cut off abruptly? Does it loop well?",
    "emotional_arc": "What emotion or feeling does this video evoke? Does the emotional intensity change over time, or stay constant?",
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
    print("Qwen model loaded.")
    return model, processor


def query_qwen_on_video(model, processor, video_path, question, max_new_tokens=300):
    import torch
    from qwen_vl_utils import process_vision_info
    messages = [{"role": "user", "content": [
        {"type": "video", "video": video_path, "max_pixels": 360*420, "fps": 1.0},
        {"type": "text", "text": question},
    ]}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                       padding=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
    trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
    return processor.batch_decode(trimmed, skip_special_tokens=True,
                                  clean_up_tokenization_spaces=False)[0].strip()


def run_perception(video_path, model_cache=None):
    import torch
    model, processor = load_qwen_model(model_cache)
    print("Running visual perception questions...")
    perception = {}
    for key, question in PERCEPTION_QUESTIONS.items():
        print(f"  -> {key}")
        try:
            perception[key] = query_qwen_on_video(model, processor, video_path, question)
        except Exception as e:
            perception[key] = f"[error: {e}]"
            print(f"     error: {e}")
    del model, processor
    torch.cuda.empty_cache()
    return perception


DIAGNOSTIC_SYSTEM_PROMPT = """You are a senior creative strategist analyzing why a short-form video may underperform on engagement. You are given FOUR sources of evidence:

1. **Visual perception report** (Qwen2.5-VL) — what's in the video
2. **Key-frame analysis** — WHEN the highest-attention visual moments occur
3. **Audio analysis** (Whisper + librosa) — transcript, energy, silences, character
4. **Predicted gaze tracking** (TASED-Net, trained on real human eye-tracking) — WHERE viewers' eyes are predicted to look

Your job:
1. Identify the top 3 specific risks to engagement, ranked by likely impact.
2. For each risk, cite specific evidence from across the four signals.
3. Suggest a concrete, testable fix.

Pay special attention to GAZE-CONTENT MISMATCH:
- Where do the predicted eyes go vs. where the important content is?
- If the product is in zone X but eyes go to zone Y, that's a critical finding.
- If eyes are stable (high focus) on the intended subject, that's a strength.
- If eyes wander across many zones, the visual hierarchy may be unclear.

Also AUDIO-VISUAL ALIGNMENT and TIMING (early hooks vs late peaks).

Be honest and direct. Every observation must reference specific evidence. Frame issues as hypotheses, not certainties.

CAVEAT: TASED-Net was trained on landscape natural video. Predictions on vertical short-form are approximate. Mention this in caveats.

Output strict JSON:
{
  "summary": "1-2 sentence assessment",
  "strengths": ["..."],
  "risks": [{"rank": 1, "issue": "...", "evidence": "...", "impact": "...", "suggested_fix": "...", "confidence": "high|medium|low"}],
  "gaze_analysis": "Where eyes are predicted to land vs. where the important content is",
  "audio_visual_alignment": "Whether audio and visuals work together",
  "key_moments_analysis": "Whether high-attention timestamps align with good patterns",
  "diagnostic_caveats": "What this analysis cannot tell you, including saliency model limitations"
}
"""


def run_diagnosis(perception, keyframe_meta, audio_report, saliency_meta,
                  video_path, title=None, description=None):
    from anthropic import Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    client = Anthropic(api_key=api_key)
    perception_text = "\n\n".join(f"## {k.upper()}\n{v}" for k, v in perception.items())
    kf_section = f"Video duration: {keyframe_meta.get('duration_sec', '?')}s\n\n"
    kf_section += "Top visual attention moments:\n"
    for kf in keyframe_meta.get("key_frames", []):
        kf_section += f"  - t={kf['timestamp']}s score={kf['composite_score']} (motion={kf['motion_norm']})\n"
    timeline = keyframe_meta.get("score_timeline", [])
    if timeline:
        kf_section += "\nTimeline: " + " ".join(f"{p['t']}s={p['score']:.1f}" for p in timeline[:30])
    audio_section = audio_report.get("diagnostic_summary", "(unavailable)")
    saliency_section = saliency_meta.get("diagnostic_summary", "(unavailable)")
    user_message = (
        f"Video: {os.path.basename(video_path)}\n"
        f"Title: {title or '(none)'}\nDescription: {description or '(none)'}\n\n"
        f"VISUAL PERCEPTION (Qwen2.5-VL):\n\n{perception_text}\n\n"
        f"KEY-FRAMES:\n\n{kf_section}\n\n"
        f"AUDIO (Whisper+librosa):\n\n{audio_section}\n\n"
        f"GAZE PREDICTION (TASED-Net):\n\n{saliency_section}\n\n"
        f"Produce diagnostic JSON."
    )
    print("Sending to Claude for diagnostic synthesis...")
    response = client.messages.create(
        model="claude-opus-4-7", max_tokens=3500,
        system=DIAGNOSTIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--output", default="report.json")
    parser.add_argument("--model-cache", default="/content/drive/MyDrive/lmm_evqa/qwen_cache")
    parser.add_argument("--num-keyframes", type=int, default=4)
    parser.add_argument("--whisper-size", default="base")
    parser.add_argument("--tased-weights", default="/content/drive/MyDrive/lmm_evqa/tased_weights/TASED_updated.pt")
    args = parser.parse_args()
    if not os.path.exists(args.video_path):
        print(f"ERROR: {args.video_path} not found"); sys.exit(1)
    os.makedirs(args.model_cache, exist_ok=True)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    print("\n--- STEP 1: Key-frames ---")
    from extract_keyframes import extract_keyframes
    keyframe_dir = args.output.replace(".json", "_keyframes")
    keyframe_meta = extract_keyframes(args.video_path, keyframe_dir, num_frames=args.num_keyframes)

    print("\n--- STEP 2: Audio ---")
    from analyze_audio import analyze_audio
    audio_report = analyze_audio(args.video_path, whisper_model_size=args.whisper_size)
    audio_path = args.output.replace(".json", "_audio.json")
    with open(audio_path, "w") as f:
        json.dump(audio_report, f, indent=2, cls=_NumpyJSONEncoder)

    print("\n--- STEP 3: Saliency (TASED-Net) ---")
    from saliency_module import analyze_saliency
    saliency_dir = args.output.replace(".json", "_saliency")
    saliency_meta = analyze_saliency(args.video_path, tased_weights_path=args.tased_weights,
                                      output_dir=saliency_dir)

    print("\n--- STEP 4: Visual perception (Qwen) ---")
    perception = run_perception(args.video_path, model_cache=args.model_cache)
    perception_path = args.output.replace(".json", "_perception.json")
    with open(perception_path, "w") as f:
        json.dump(perception, f, indent=2, cls=_NumpyJSONEncoder)

    print("\n--- STEP 5: Synthesis ---")
    diagnosis = run_diagnosis(perception, keyframe_meta, audio_report, saliency_meta,
                              args.video_path, args.title, args.description)

    report = {
        "video_path": args.video_path, "title": args.title, "description": args.description,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model_stack": "Qwen2.5-VL + Whisper + Key-frames + TASED-Net + Claude",
        "key_frames": {"directory": keyframe_dir, "metadata": keyframe_meta},
        "audio": audio_report,
        "saliency": {
            "overlay_video": saliency_meta.get("overlay_video"),
            "sample_frames_dir": saliency_meta.get("sample_frames_dir"),
            "gaze_at_keyframes": saliency_meta.get("gaze_at_keyframes"),
            "diagnostic_summary": saliency_meta.get("diagnostic_summary"),
        },
        "perception": perception, "diagnosis": diagnosis,
    }
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, cls=_NumpyJSONEncoder)
    print(f"\n✅ Full report saved to {args.output}")
    print(f"✅ Saliency overlay: {saliency_meta.get('overlay_video')}")

    print("\n" + "=" * 60); print("DIAGNOSTIC SUMMARY"); print("=" * 60)
    if "summary" in diagnosis:
        print(f"\n{diagnosis['summary']}")
        if diagnosis.get("strengths"):
            print("\nStrengths:")
            for s in diagnosis["strengths"]: print(f"  + {s}")
        print("\nTop risks:")
        for r in diagnosis.get("risks", []):
            print(f"\n  #{r.get('rank')}: {r.get('issue')}  [{r.get('confidence', '?')}]")
            print(f"     Evidence: {r.get('evidence')}")
            print(f"     Impact:   {r.get('impact')}")
            print(f"     Fix:      {r.get('suggested_fix')}")
        if "gaze_analysis" in diagnosis: print(f"\nGaze: {diagnosis['gaze_analysis']}")
        if "audio_visual_alignment" in diagnosis: print(f"\nA/V: {diagnosis['audio_visual_alignment']}")
        if "key_moments_analysis" in diagnosis: print(f"\nKey moments: {diagnosis['key_moments_analysis']}")
        if "diagnostic_caveats" in diagnosis: print(f"\nCaveats: {diagnosis['diagnostic_caveats']}")
    else:
        print(json.dumps(diagnosis, indent=2))


if __name__ == "__main__":
    main()
