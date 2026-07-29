import modal
import math
import os
import re
import json
import base64
import subprocess
import uuid
import threading

# GPU image with all deps + ffmpeg
image = (
    modal.Image.debian_slim()
    .pip_install(
        "fastapi", "uvicorn", "python-multipart",
        "torch", "torchvision", "transformers", "qwen-vl-utils", "accelerate",
        "opencv-contrib-python", "numpy", "librosa", "openai-whisper",
        "yt-dlp", "anthropic>=0.117.0", "Pillow", "scipy",
    )
    .run_commands("apt-get update && apt-get install -y ffmpeg")
)

assets_volume = modal.Volume.from_name("fixation-assets")
hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)

# Distributed job store — survives container restarts (redeploys) and is shared
# across replicas, so a status poll can't miss a job submitted to another container.
# Replaces a per-container in-memory dict that produced "Job lost" on restart/scale.
JOBS = modal.Dict.from_name("fixation-jobs", create_if_missing=True)

app = modal.App(name="fixation-api", image=image)

# Paths inside the container
SCRIPTS_DIR = "/mnt/fixation-assets"                    # scripts now live at root
NESTED = "/mnt/fixation-assets/fixation-assets"         # weights/benchmarks are nested here
TASED_WEIGHTS = f"{NESTED}/tased_weights/TASED_updated.pt"
# Percentile benchmarks (full sets, computed in-house). Pick by asset format so a
# digital KV is scored against the online gallery and print/OOH against e-paper.
# (The old advert_gallery set is only 194 images — kept only as a last-resort fallback.)
BENCHMARKS = {
    "online": f"{NESTED}/benchmarks/benchmark_online_percentiles.json",      # 12,680 ads
    "epaper": f"{NESTED}/benchmarks/benchmark_epaper1_percentiles.json",     # 15,408 ads
    "gallery": f"{NESTED}/benchmarks/benchmark_advert_gallery_percentiles.json",  # 194 (fallback)
}
_FORMAT_BENCHMARK = {
    "social": "online", "banner": "online", "kv": "online", "digital": "online",
    "print": "epaper", "ooh": "epaper",
}


def benchmark_for(format_type):
    """Select the percentile benchmark for an asset format; default to the online set."""
    key = _FORMAT_BENCHMARK.get((format_type or "").strip().lower(), "online")
    return BENCHMARKS[key]
TASED_REPO = f"{NESTED}/TASED-Net"                      # saliency_module hardcodes /content/TASED-Net
MODEL_CACHE = "/hf-cache"


def _setup_paths():
    """saliency_module.py hardcodes /content/TASED-Net; symlink it to the real repo."""
    os.makedirs("/content", exist_ok=True)
    link = "/content/TASED-Net"
    if not os.path.islink(link) and not os.path.exists(link):
        os.symlink(TASED_REPO, link, target_is_directory=True)


# ─────────────────────────────────────────────────────────────────────────────
# Funnel-aware engagement scoring
# Adds a focused vision-LLM judgment (commercial context, emotion, brand, persuasion,
# trust) on top of the measured CV KPIs, then aggregates both into 5 funnel-specific
# KPIs + a single Engagement Potential score. Canonical prompt copy lives in the repo
# at f1x8_engagement_prompt.txt; it is embedded here so it ships with the Modal deploy.
# ─────────────────────────────────────────────────────────────────────────────

ENGAGEMENT_PROMPT = """You are the F1X8 engagement assessor. You evaluate an advertising asset (static KV, social creative, display, OOH, or video) and predict its ENGAGEMENT POTENTIAL: how likely it is to earn attention and interaction in-feed.

You do NOT score visual measurements. A separate computer-vision pipeline already measures attention concentration (saliency), contrast, layout density, edge complexity, and gaze behaviour. Your job is to assess only what cannot be measured: commercial context, emotional pull, brand attribution, distinctiveness, persuasive intent, and trust. Be decisive and concrete. Ground every judgment in something visible in the asset.

Output a single valid JSON object. No preamble, no markdown fences, no commentary outside the JSON. Every field must be populated. Never return null for a text field; use "Not detected" or "N/A".

CORE PRINCIPLE: COMMERCIAL CONTEXT DRIVES ENGAGEMENT
A hard offer ("50% off, ends Sunday") drives engagement and clicks regardless of how elegant the design is. A pure-brand awareness piece drives engagement through emotion and distinctiveness, not offers. You must classify the asset correctly so it is judged against the right standard. Do not penalize an awareness asset for lacking an offer, and do not over-credit a weak offer asset just because it has a discount.

SCORING DISCIPLINE - USE THE FULL 0-10 RANGE
You are a demanding, discriminating critic, not a brand-friendly reviewer. Score against an absolute, best-in-class standard - NOT relative to "it is a professional ad, so it must be good." Most production ads are competent but unremarkable, and competent is a 5, not an 8.
- Calibrate every dimension to this anchor: 0-3 = genuinely weak (generic, off-brand, confusing, flat); 4-6 = competent but unremarkable, the median ad; 7-8 = clearly strong, a cut above the category; 9-10 = exceptional, reference-quality work you would hold up as a benchmark.
- Do NOT cluster scores in 7-9. If most of your scores are 7+, you are being too generous - push them down. A score of 9 must be rare and earned.
- Before scoring each dimension, name the single biggest weakness of THIS asset on that dimension, then score. A high score must be justified by something specifically visible, never granted by default.
- Score each dimension independently and decisively. Two different assets should rarely receive identical scores - if you find yourself repeating the same numbers, look harder for what separates them.
- Score dimensions independently of each other: a strong brand must not lift emotional_pull, and a hard offer must not lift trust_credibility. Before output, re-read your five scores - if three or more share the same value, you have defaulted; re-differentiate using the band anchors.
- Each band anchor below describes something you can literally point to in the asset. Score to the band whose description matches what you see, not to a general impression of quality.

IN-FEED CALIBRATION - GROUNDED IN MEASURED ORGANIC ENGAGEMENT
These corrections come from comparing judge scores against realized engagement on real brand social creatives. Where they conflict with an instinct above, they win:
- Confident teaser minimalism is a code-break, not an absence. A typography-only announcement, an unbranded product silhouette in dramatic light, or a near-black close-up that deliberately withholds the product signals a launch moment and generates anticipation. Score the withholding as curiosity (emotional_pull 6-8) and the code-break as distinctiveness (6-8); do not give brand_strength 1-3 when the silhouette, colour world, or launch style is identifiable - the restraint IS the brand acting like a leader.
- Capability-proof imagery - a photograph presented as the product's own camera output (night sky, wildlife, low light), often with no product or logo in frame - attributes through the "shot on" convention and is among the strongest organic engagement devices. brand_strength 5-7 and emotional_pull 6-8; never 1-2 for a missing logo.
- Internet-native formats (meme split-panels, self-aware platform humor, trend formats) are top-decile in-feed engagement devices: distinctiveness 7-9 even when the craft is deliberately rough, and never penalize persuasive_power on such an asset for lacking an offer.
- Polished showcase craft is the real category cliche in-feed: device-hero-on-gradient, product staged in a styled interior, event/exhibition glamour shots, sports-action composites bursting off a TV screen. However clean the execution, these are distinctiveness 3-5 and emotional_pull 3-5 unless a genuinely novel device is present. Production sheen must not lift any score.
- Clarity of a low-interest message is not engagement. An event invitation, appliance feature explainer, or ecosystem how-to can have message_clarity 9 and still die in-feed; score the other dimensions honestly rather than letting a clean layout halo them.

STEP 1: CLASSIFY CONTEXT

funnel_stage:
- "upper" (awareness): builds brand, emotion, recall. No offer or a soft one. Engagement comes from attention, emotion, and distinctiveness.
- "mid" (consideration): explains product value, features, comparison. Mixed intent.
- "lower" (conversion): drives a specific action. Offer, price, promo, urgency, strong CTA. Engagement comes from offer strength, clarity, and trust.

product_tier: "mass" | "mid" | "premium" | "luxury". Affects expected restraint, copy density, and tone.

asset_intent: "brand" (no commercial offer) | "offer" (discount, price, promo, time-limited) | "hybrid" (brand message with a commercial element).

STEP 2: SCORE THE JUDGMENT KPIs (0-10 each)
Score ALL of the following. The website surfaces a different subset depending on funnel stage, but you always return every score.

EMOTIONAL PULL (0-10) [surfaced for upper and mid funnel]
Strength of emotional or aspirational response the asset triggers.
- Identify the primary emotion (aspiration, excitement, trust, joy, curiosity, FOMO, belonging, pride, relief, desire).
- Is there storytelling or identity signal beyond the product, or a flat product showcase?
- If people are present: is the expression and body language authentic and resonant?
- Band anchors:
  8-10: a nameable human story, tension, or identity claim that would still be interesting with the product removed. 9+ only when the emotional idea is the organizing concept of the entire asset.
  6-7: deliberate mood or aspiration built through casting, styling, colour world, or world-building - or deliberate anticipation: a teaser that withholds the product or message to create curiosity. No story you could retell in one sentence.
  4-5: polished product aesthetic only; any feeling comes from production sheen, not an idea. The median production ad lives here.
  2-3: purely informational or transactional layout; no visible emotional intent.
  0-1: tone actively off-putting, confused, or contradictory.

BRAND STRENGTH (0-10) [surfaced for all funnels]
How strongly the asset attributes to its brand and how confidently the brand shows up.
- Is the logo present and clearly placed?
- attribution_without_logo: if the logo were covered, could you still identify the brand from colour, type, and style? High = distinctive system. Low = interchangeable.
- Attribution can be earned without any logo: an iconic product silhouette, a proprietary colour world, or the "shot on [product]" camera-proof convention all attribute.
- Does colour and typography feel brand-consistent and deliberate, or approximated?
- Band anchors:
  8-10: cover the logo and the brand is still identifiable within a second (distinctive colour world, type voice, iconic product silhouette). Reserve 9-10 for assets that could ONLY be this brand. A clear logo on an otherwise interchangeable layout does NOT reach this band.
  6-7: logo clear and confidently placed, brand palette respected - but covered-logo attribution would take effort or guesswork.
  4-5: logo present but passive; the visual system is category-generic. The median production ad lives here.
  2-3: logo hard to find, or brand cues inconsistent with the brand's identity.
  0-1: no attribution at all.

DISTINCTIVENESS (0-10) [surfaced for upper funnel]
How much the asset stands apart from the visual conventions of its product category.
- Does it look different from what competitors in this category typically produce, or is it a category cliche?
- Distinctive creative is remembered and re-engaged; generic creative is scrolled past even when competent.
- Band anchors:
  8-10: a visual or conceptual device you have not seen in this category - name it in your reasoning. It would stop a viewer who has already scrolled past 50 category ads today.
  6-7: a familiar format executed with a noticeable twist or clearly superior craft; the format itself is still standard.
  4-5: textbook category convention executed competently (for smartphones: device hero at angle + gradient background + feature line; for TVs and appliances: product staged in a styled interior, or sports/action imagery bursting off the screen - all 4-5 by definition). The median production ad lives here.
  2-3: interchangeable with any competitor; template feel; nothing to remember it by.
  0-1: derivative to the point of confusion with another brand's work.

TALKABILITY (0-10) [surfaced for upper funnel]
Would a scrolling viewer interact with this — comment, share, tag someone, save? This is the mechanism that actually moves feeds; it is validated against realized organic engagement.
- Is there a conversation hook: a question, a take, an in-joke, a "which one are you" identity prompt, something to disagree with?
- Would someone send this to a specific friend, and why? Name the friend-shaped reason (relatable situation, shared fandom, useful flex, humor).
- Is there a cultural or moment hook (trend format, event tie-in, celebrity/fandom signal) that gives it social currency?
- Band anchors:
  8-10: a built-in reason to respond or share that you can name in one sentence (identity prompt, fandom signal, genuinely funny or provocative take). The interaction is the point of the asset.
  6-7: clear social currency — a moment, meme format, or fandom cue — but the viewer is a spectator, not invited into the conversation.
  4-5: pleasant and well-made with nothing to say back to it; would earn a pause, not a comment. The median production ad lives here.
  2-3: purely informational; interacting with it would feel odd.
  0-1: actively repels interaction (corporate wall of text, stock-photo sterility).

PERSUASIVE POWER (0-10) [surfaced for lower and mid funnel]
Strength of the asset's pull toward action. Absorbs all offer and CTA logic. Main engagement driver for lower-funnel assets.
- offer_present: discount, price, promotion, bundle, or value claim?
- offer_aggressiveness: "none" | "soft" (gentle value mention) | "moderate" (clear discount or price) | "hard" (large discount, dramatic value, loss-framed).
- cta_strength: "absent" | "passive" ("Learn more") | "specific" ("Shop Galaxy AI") | "urgent" ("Buy now, ends Sunday").
- urgency_signals: time-limited or quantity-limited cues present (true/false).
- Scoring: hard offer with an urgent, specific CTA scores 8-10. Clear offer with a specific CTA scores 6-8. Soft value message scores 4-6. Pure-brand asset with no commercial pull scores 1-3, and that is correct for an awareness asset; the website weighting handles it.

TRUST & CREDIBILITY (0-10) [surfaced for lower funnel]
Strength of trust signals that reduce friction to action.
- Ratings, review counts, money-back guarantee, secure payment, official partner or carrier badges, warranty, certifications.
- For a conversion asset, weak trust signal suppresses action even with a strong offer.
- High (8-10): multiple credible trust markers prominent. Mid (5-7): some present. Low (0-4): none, or none appropriate to the offer.
- For a pure-brand awareness asset with no conversion intent, score 5 (neutral, not applicable) and note "N/A for awareness".

STEP 3: MESSAGE CLARITY JUDGMENT (supports the measured clarity KPI)
- three_second_pass: can a cold viewer extract this stage's core message within 3 seconds? The core message is FUNNEL-CONDITIONAL — judge only against what this stage owes the viewer:
  upper: brand + the idea or feeling. NO action or offer is required; a deliberate teaser that withholds product detail still passes if the brand and intrigue land.
  mid: brand + product + the key benefit or feature.
  lower: brand + offer + the action to take.
- biggest_blocker: the single biggest comprehension blocker (competing messages, buried hook, illegible key text), or "None". A missing CTA/offer is NEVER the blocker for an upper-funnel asset.

STEP 4: ENGAGEMENT DRIVERS
- primary_engagement_driver: the single strongest reason this asset will earn engagement.
- primary_engagement_risk: the single biggest reason it may underperform AT ITS OWN FUNNEL STAGE. Never name the absence of another stage's device (missing CTA/offer/price on upper funnel; density or commercial tone on lower funnel) as the risk — find the weakness within the job this asset is doing.

OUTPUT FORMAT (return only this object):

{
  "funnel_stage": "upper | mid | lower",
  "funnel_reasoning": "string",
  "product_tier": "mass | mid | premium | luxury",
  "asset_intent": "brand | offer | hybrid",
  "emotional_pull": {
    "score": 0,
    "primary_emotion": "string",
    "storytelling_present": true,
    "reasoning": "string"
  },
  "brand_strength": {
    "score": 0,
    "logo_present": true,
    "attribution_without_logo": "high | medium | low",
    "reasoning": "string"
  },
  "distinctiveness": {
    "score": 0,
    "reasoning": "string"
  },
  "talkability": {
    "score": 0,
    "conversation_hook": "string",
    "reasoning": "string"
  },
  "persuasive_power": {
    "score": 0,
    "offer_present": true,
    "offer_aggressiveness": "none | soft | moderate | hard",
    "cta_strength": "absent | passive | specific | urgent",
    "urgency_signals": true,
    "reasoning": "string"
  },
  "trust_credibility": {
    "score": 0,
    "signals_present": "string",
    "reasoning": "string"
  },
  "message_clarity_judgment": {
    "three_second_pass": true,
    "biggest_blocker": "string"
  },
  "primary_engagement_driver": "string",
  "primary_engagement_risk": "string"
}"""


# Structured-output schema for the engagement judgment. Mirrors the OUTPUT
# FORMAT block in ENGAGEMENT_PROMPT; passed as output_config.format so the API
# guarantees syntactically valid JSON (a ~11% rate of trailing-comma/other
# malformed responses was observed without it — each one silently became the
# neutral 5.0 default and the "mid" funnel via _neutral_engagement()).
# Only schema features supported by structured outputs are used
# (type/enum/properties/required/additionalProperties).
ENGAGEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "funnel_stage": {"type": "string", "enum": ["upper", "mid", "lower"]},
        "funnel_reasoning": {"type": "string"},
        "product_tier": {"type": "string", "enum": ["mass", "mid", "premium", "luxury"]},
        "asset_intent": {"type": "string", "enum": ["brand", "offer", "hybrid"]},
        "emotional_pull": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "primary_emotion": {"type": "string"},
                "storytelling_present": {"type": "boolean"},
                "reasoning": {"type": "string"},
            },
            "required": ["score", "primary_emotion", "storytelling_present", "reasoning"],
            "additionalProperties": False,
        },
        "brand_strength": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "logo_present": {"type": "boolean"},
                "attribution_without_logo": {"type": "string", "enum": ["high", "medium", "low"]},
                "reasoning": {"type": "string"},
            },
            "required": ["score", "logo_present", "attribution_without_logo", "reasoning"],
            "additionalProperties": False,
        },
        "distinctiveness": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "reasoning": {"type": "string"},
            },
            "required": ["score", "reasoning"],
            "additionalProperties": False,
        },
        "talkability": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "conversation_hook": {"type": "string"},
                "reasoning": {"type": "string"},
            },
            "required": ["score", "conversation_hook", "reasoning"],
            "additionalProperties": False,
        },
        "persuasive_power": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "offer_present": {"type": "boolean"},
                "offer_aggressiveness": {"type": "string", "enum": ["none", "soft", "moderate", "hard"]},
                "cta_strength": {"type": "string", "enum": ["absent", "passive", "specific", "urgent"]},
                "urgency_signals": {"type": "boolean"},
                "reasoning": {"type": "string"},
            },
            "required": ["score", "offer_present", "offer_aggressiveness",
                         "cta_strength", "urgency_signals", "reasoning"],
            "additionalProperties": False,
        },
        "trust_credibility": {
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "signals_present": {"type": "string"},
                "reasoning": {"type": "string"},
            },
            "required": ["score", "signals_present", "reasoning"],
            "additionalProperties": False,
        },
        "message_clarity_judgment": {
            "type": "object",
            "properties": {
                "three_second_pass": {"type": "boolean"},
                "biggest_blocker": {"type": "string"},
            },
            "required": ["three_second_pass", "biggest_blocker"],
            "additionalProperties": False,
        },
        "primary_engagement_driver": {"type": "string"},
        "primary_engagement_risk": {"type": "string"},
    },
    "required": ["funnel_stage", "funnel_reasoning", "product_tier", "asset_intent",
                 "emotional_pull", "brand_strength", "distinctiveness", "talkability",
                 "persuasive_power", "trust_credibility", "message_clarity_judgment",
                 "primary_engagement_driver", "primary_engagement_risk"],
    "additionalProperties": False,
}


def _neutral_engagement():
    """Neutral default so the pipeline never crashes when the LLM/JSON fails."""
    judgment = {"score": 5, "reasoning": ""}
    return {
        "funnel_stage": "mid",
        "product_tier": "mid",
        "asset_intent": "hybrid",
        "emotional_pull": dict(judgment),
        "brand_strength": dict(judgment),
        "distinctiveness": dict(judgment),
        "talkability": dict(judgment),
        "persuasive_power": dict(judgment),
        "trust_credibility": dict(judgment),
        "message_clarity_judgment": {"three_second_pass": True, "biggest_blocker": "None"},
        "primary_engagement_driver": "Not detected",
        "primary_engagement_risk": "Not detected",
    }


def _parse_engagement_json(text):
    """Strip accidental code fences / prose and json.loads the object. None on
    failure — a failed parse must not enter the ensemble as a fake neutral vote;
    assess_engagement falls back to neutral only when every sample fails."""
    if not text:
        return None
    try:
        t = text.strip()
        if t.startswith("```"):
            t = t.split("```", 2)[1] if "```" in t[3:] else t.lstrip("`")
            if t.startswith("json"):
                t = t[4:]
        start = t.find("{")
        end = t.rfind("}")
        if start == -1 or end == -1:
            return None
        t = t[start:end + 1]
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            # The judge occasionally emits trailing commas ("...",\n}) — the
            # dominant observed failure mode. Repair rather than discarding the
            # whole judgment for neutral defaults.
            return json.loads(re.sub(r",(\s*[}\]])", r"\1", t))
    except Exception as e:
        print(f"engagement JSON parse failed: {e}")
        return None


def _media_type(path):
    try:
        from PIL import Image
        fmt = Image.open(path).format
        return {
            "JPEG": "image/jpeg", "PNG": "image/png",
            "WEBP": "image/webp", "GIF": "image/gif",
        }.get(fmt, "image/jpeg")
    except Exception:
        return "image/jpeg"


def _sample_frames(video_path, n=3):
    """Sample n evenly-spaced keyframes as (media_type, base64) for the vision LLM."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        frames = []
        idxs = [int(total * (i + 1) / (n + 1)) for i in range(n)] if total > 0 else []
        for idx in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            ok2, buf = cv2.imencode(".jpg", frame)
            if not ok2:
                continue
            frames.append(("image/jpeg", base64.b64encode(buf.tobytes()).decode("utf-8")))
        cap.release()
        return frames
    except Exception as e:
        print(f"frame sampling failed: {e}")
        return []


JUDGE_SAMPLES = 3  # median-of-N judge ensemble; see eval/ reliability harness


def _assess_engagement_once(images):
    """One vision-LLM judge call. Returns the parsed judgment, or None on failure."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": mt, "data": d}}
            for mt, d in images
        ]
        content.append({
            "type": "text",
            "text": "Assess this advertising asset for engagement potential. Return only the JSON object.",
        })
        resp = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1500,
            system=ENGAGEMENT_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": ENGAGEMENT_SCHEMA}},
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return _parse_engagement_json(text)
    except Exception as e:
        import traceback
        print(f"[engagement] sample FAILED ({type(e).__name__}): {e}")
        print(traceback.format_exc()[-600:])
        return None


_JUDGED_KPI_FIELDS = ["emotional_pull", "brand_strength", "distinctiveness",
                      "talkability", "persuasive_power", "trust_credibility"]


def _kpi_score(judgment, kpi):
    try:
        return float((judgment.get(kpi) or {}).get("score", 5))
    except (TypeError, ValueError, AttributeError):
        return 5.0


def _majority(values, tie_breaker=None):
    """Most common non-None value. Ties go to tie_breaker when it is among the
    tied values, else to a sorted pick — never to arrival order, which would
    make the aggregate depend on which parallel API call returned first."""
    from collections import Counter
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    counts = Counter(vals)
    top = max(counts.values())
    tied = [v for v, c in counts.items() if c == top]
    if len(tied) == 1:
        return tied[0]
    if tie_breaker in tied:
        return tie_breaker
    return min(tied, key=repr)


def _aggregate_judgments(judgments):
    """Component-wise median/majority across judge samples. Text fields are
    copied from the sample nearest the aggregate so reasoning always matches
    a real judgment rather than a stitched-together one. Vote ties are broken
    by the medoid sample (the one closest to the KPI medians)."""
    if len(judgments) == 1:
        return judgments[0]
    import json  # local, so AST-extracted copies (eval/) stay self-contained
    import statistics

    # Canonical order so every tie-break (medoid, nearest-sample, vote counts)
    # is independent of which parallel API call happened to return first.
    judgments = sorted(judgments, key=lambda j: json.dumps(j, sort_keys=True))

    medians = {k: statistics.median(_kpi_score(j, k) for j in judgments)
               for k in _JUDGED_KPI_FIELDS}
    medoid = min(judgments, key=lambda j: sum(abs(_kpi_score(j, k) - medians[k])
                                              for k in _JUDGED_KPI_FIELDS))

    agg = {}
    for field in ("funnel_stage", "product_tier", "asset_intent"):
        agg[field] = _majority([j.get(field) for j in judgments], medoid.get(field))
    stage_src = next((j for j in judgments if j.get("funnel_stage") == agg["funnel_stage"]),
                     judgments[0])
    agg["funnel_reasoning"] = stage_src.get("funnel_reasoning", "")

    for k in _JUDGED_KPI_FIELDS:
        src = min(judgments, key=lambda j: abs(_kpi_score(j, k) - medians[k]))
        agg[k] = dict(src.get(k) or {})
        agg[k]["score"] = medians[k]

    passes = [(j.get("message_clarity_judgment") or {}).get("three_second_pass")
              for j in judgments]
    vote = _majority(passes,
                     (medoid.get("message_clarity_judgment") or {}).get("three_second_pass"))
    clarity_src = next((j for j in judgments
                        if (j.get("message_clarity_judgment") or {}).get("three_second_pass") == vote),
                       judgments[0])
    agg["message_clarity_judgment"] = dict(clarity_src.get("message_clarity_judgment") or {})

    for field in ("primary_engagement_driver", "primary_engagement_risk"):
        agg[field] = medoid.get(field, "Not detected")
    return agg


def assess_engagement(images):
    """Median-of-N ensemble over the vision-LLM judge; parse JSON robustly.
    images: list of (media_type, base64_data). Returns the aggregated judgment
    or a neutral default.

    A single judge call shows per-KPI test-retest std up to ~0.5 (±1-point
    swings on the KPIs the site displays — see eval/README.md); the
    component-wise median of JUDGE_SAMPLES parallel calls suppresses those
    swings at unchanged latency."""
    if not images:
        print("[engagement] no images supplied -> neutral default")
        return _neutral_engagement()
    print(f"[engagement] calling vision LLM x{JUDGE_SAMPLES} with {len(images)} image(s); "
          f"ANTHROPIC_API_KEY set={bool(os.environ.get('ANTHROPIC_API_KEY'))}")
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=JUDGE_SAMPLES) as ex:
        samples = [s for s in ex.map(lambda _: _assess_engagement_once(images),
                                     range(JUDGE_SAMPLES)) if s is not None]
    if not samples:
        print("[engagement] all samples FAILED -> neutral default")
        return _neutral_engagement()
    try:
        parsed = _aggregate_judgments(samples)
        print(f"[engagement] OK n={len(samples)} funnel={parsed.get('funnel_stage')} "
              f"emo={parsed.get('emotional_pull', {}).get('score')} "
              f"brand={parsed.get('brand_strength', {}).get('score')} "
              f"persuasive={parsed.get('persuasive_power', {}).get('score')}")
        return parsed
    except Exception as e:
        import traceback
        print(f"[engagement] aggregation FAILED ({type(e).__name__}): {e}")
        print(traceback.format_exc()[-600:])
        return _neutral_engagement()


def _score_of(v):
    """Measured KPI value may be a number or a {score: ...} object."""
    if isinstance(v, dict):
        return v.get("score", v.get("value"))
    return v


def _blend(measured, weights):
    """sum(score * weight) over present keys, renormalized over the weights that were found."""
    acc = 0.0
    total_w = 0.0
    for k, w in weights.items():
        s = _score_of(measured.get(k))
        if s is None:
            continue
        try:
            acc += float(s) * w
            total_w += w
        except (TypeError, ValueError):
            continue
    return acc / total_w if total_w else 5.0


_ATTENTION_SRC = {"image": "hierarchy", "video": "first_fixation"}
_CLARITY_SRC = {"image": "text_balance", "video": "cognitive_load"}

# Upper funnel surfaces talkability instead of message_clarity: clarity was
# zero-to-negative signal for realized organic engagement on awareness assets
# (calibration study, eval/calibration/FINDINGS.md), while share/comment
# provocation is the mechanism feeds actually reward. Clarity still gates the
# score indirectly via three_second_pass and remains surfaced for mid/lower.
_FUNNEL_SELECT = {
    "upper": ["attention_capture", "emotional_pull", "brand_strength", "distinctiveness", "talkability"],
    "lower": ["persuasive_power", "message_clarity", "attention_capture", "trust_credibility", "brand_strength"],
    "mid": ["attention_capture", "persuasive_power", "message_clarity", "emotional_pull", "brand_strength"],
}
_FUNNEL_WEIGHTS = {
    "upper": {"attention_capture": .24, "emotional_pull": .26, "brand_strength": .18, "distinctiveness": .14, "talkability": .18},
    "lower": {"persuasive_power": .34, "message_clarity": .22, "attention_capture": .18, "trust_credibility": .16, "brand_strength": .10},
    "mid": {"attention_capture": .22, "persuasive_power": .22, "message_clarity": .20, "emotional_pull": .18, "brand_strength": .18},
}

# Bradley-Terry weights refit against realized organic engagement
# (eval/finetune/analyze_weights.py, 2026-07-28 study). Negative weights are
# real: in-feed, clarity/attention polish anti-correlates with organic pull.
_ORGANIC_WEIGHTS = {
    "attention_capture": -0.347, "emotional_pull": 0.409, "brand_strength": 1.107,
    "distinctiveness": 0.363, "persuasive_power": 0.525, "trust_credibility": 0.209,
    "message_clarity": -0.371,
}


def aggregate_engagement(measured, judgment, media_type, funnel):
    """Map measured CV KPIs + LLM judgment into 5 funnel-specific KPIs and one
    Engagement Potential score. Returns (engagement_potential, kpis_dict)."""
    def jscore(name):
        try:
            return float((judgment.get(name) or {}).get("score", 5))
        except (TypeError, ValueError):
            return 5.0

    def jreason(name):
        return (judgment.get(name) or {}).get("reasoning") or ""

    def methodology(key, default):
        v = measured.get(key)
        if isinstance(v, dict) and v.get("methodology"):
            return v["methodology"]
        return default

    if media_type == "video":
        attention = _blend(measured, {"first_fixation": 0.4, "hook": 0.3, "pattern_interrupt": 0.3})
        clarity = _blend(measured, {"cognitive_load": 0.5, "switching_cost": 0.5})
    else:
        # NOTE: the image CV pipeline emits keys `contrast` and `complexity`
        # (not `color_contrast` / `visual_complexity` as the brief stated).
        attention = _blend(measured, {"hierarchy": 0.5, "contrast": 0.3, "composition": 0.2})
        clarity = _blend(measured, {"text_balance": 0.4, "complexity": 0.35, "white_space": 0.25})

    if (judgment.get("message_clarity_judgment") or {}).get("three_second_pass") is False:
        clarity *= 0.85

    all_kpis = {
        "attention_capture": {"score": round(attention, 1), "label": "Attention Capture",
                              "methodology": methodology(_ATTENTION_SRC[media_type], "Weighted blend of measured attention signals (saliency, contrast, first fixation).")},
        "message_clarity": {"score": round(clarity, 1), "label": "Message Clarity",
                            "methodology": methodology(_CLARITY_SRC[media_type], "Weighted blend of measured clarity signals (text balance, complexity, cognitive load).")},
        "emotional_pull": {"score": round(jscore("emotional_pull"), 1), "label": "Emotional Pull", "methodology": jreason("emotional_pull")},
        "brand_strength": {"score": round(jscore("brand_strength"), 1), "label": "Brand Strength", "methodology": jreason("brand_strength")},
        "distinctiveness": {"score": round(jscore("distinctiveness"), 1), "label": "Distinctiveness", "methodology": jreason("distinctiveness")},
        "talkability": {"score": round(jscore("talkability"), 1), "label": "Talkability", "methodology": jreason("talkability")},
        "persuasive_power": {"score": round(jscore("persuasive_power"), 1), "label": "Persuasive Power", "methodology": jreason("persuasive_power")},
        "trust_credibility": {"score": round(jscore("trust_credibility"), 1), "label": "Trust & Credibility", "methodology": jreason("trust_credibility")},
    }

    stage = funnel if funnel in _FUNNEL_SELECT else "mid"
    five = {kid: all_kpis[kid] for kid in _FUNNEL_SELECT[stage]}
    engagement_potential = round(sum(all_kpis[kid]["score"] * w for kid, w in _FUNNEL_WEIGHTS[stage].items()), 1)

    # Organic-context score (beta, additive): KPI weights refit against
    # realized organic engagement on brand social creatives, holdout AUC 0.69
    # vs 0.59 for the funnel-weighted score (eval/calibration/FINDINGS.md).
    # Sigmoid constants derive from the 142-creative calibration sample.
    combo = sum(all_kpis[k]["score"] * w for k, w in _ORGANIC_WEIGHTS.items())
    organic = round(10.0 / (1.0 + math.exp(-(combo - 6.989) * 0.4067)), 1)

    print(f"[engagement] aggregate stage={stage} measured_keys={list(measured.keys())} "
          f"attention={all_kpis['attention_capture']['score']} clarity={all_kpis['message_clarity']['score']} "
          f"-> engagement_potential={engagement_potential} organic={organic}")
    return engagement_potential, five, organic


@app.function(
    gpu="A10G",
    volumes={"/mnt/fixation-assets": assets_volume, "/hf-cache": hf_cache},
    timeout=1800,
    secrets=[modal.Secret.from_name("anthropic")],
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, File, UploadFile, Form
    import sys
    sys.path.insert(0, SCRIPTS_DIR)
    _setup_paths()

    web_app = FastAPI()

    def b64(path):
        if not path or not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @web_app.post("/api/analyze/image")
    async def analyze_image_endpoint(
        file: UploadFile = File(...),
        title: str = Form(None), description: str = Form(None),
        format_type: str = Form("KV"), role: str = Form("creative_director"),
    ):
        tmp = f"/tmp/upload_{file.filename}"
        with open(tmp, "wb") as f:
            f.write(await file.read())
        try:
            from analyze_image import analyze_image
            report = analyze_image(
                image_path=tmp,
                title=title or None,
                description=description or None,
                format_type=format_type,
                output_path="/tmp/image_report.json",
                model_cache=MODEL_CACHE,
                benchmark_path=benchmark_for(format_type),
                role_key=role,
            )
            overlay = report.get("saliency", {}).get("overlay_path")
            kpi_data = report.get("kpis", {})
            measured = kpi_data.get("kpis", {})
            judgment = assess_engagement([(_media_type(tmp), b64(tmp))])
            funnel = judgment.get("funnel_stage") or kpi_data.get("funnel_stage") or "mid"
            engagement_potential, five_kpis, organic = aggregate_engagement(measured, judgment, "image", funnel)
            return {
                "verdict": report.get("diagnosis", {}),
                "engagement_potential": engagement_potential,
                "score": engagement_potential,
                "organic_engagement": organic,
                "kpis": five_kpis,
                "kpis_overall": engagement_potential,
                "funnel_stage": funnel,
                "product_tier": judgment.get("product_tier") or kpi_data.get("product_tier"),
                "localization": report.get("localization"),
                "heatmap": b64(overlay),
                "heatmap_type": "image/png",
            }
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[-800:]}
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def _run_image(job_id, image_path, title, description, format_type, role):
        try:
            JOBS[job_id] = {"status": "analyzing"}
            from analyze_image import analyze_image
            report = analyze_image(
                image_path=image_path,
                title=title or None,
                description=description or None,
                format_type=format_type,
                output_path=f"/tmp/image_report_{job_id}.json",
                model_cache=MODEL_CACHE,
                benchmark_path=benchmark_for(format_type),
                role_key=role,
            )
            overlay = report.get("saliency", {}).get("overlay_path")
            kpi_data = report.get("kpis", {})
            measured = kpi_data.get("kpis", {})
            judgment = assess_engagement([(_media_type(image_path), b64(image_path))])
            funnel = judgment.get("funnel_stage") or kpi_data.get("funnel_stage") or "mid"
            engagement_potential, five_kpis, organic = aggregate_engagement(measured, judgment, "image", funnel)
            JOBS[job_id] = {
                "status": "done",
                "result": {
                    "verdict": report.get("diagnosis", {}),
                    "engagement_potential": engagement_potential,
                    "score": engagement_potential,
                    "organic_engagement": organic,
                    "kpis": five_kpis,
                    "kpis_overall": engagement_potential,
                    "funnel_stage": funnel,
                    "product_tier": judgment.get("product_tier") or kpi_data.get("product_tier"),
                    "localization": report.get("localization"),
                    "heatmap": b64(overlay),
                    "heatmap_type": "image/png",
                },
            }
        except Exception as e:
            import traceback
            JOBS[job_id] = {"status": "error", "error": str(e), "trace": traceback.format_exc()[-800:]}
        finally:
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass

    def _run_video(job_id, video_path):
        try:
            JOBS[job_id] = {"status": "analyzing"}
            out = f"/tmp/video_{job_id}.json"
            cmd = [
                "python", f"{SCRIPTS_DIR}/diagnose_video_v5.py",
                "--video-path", video_path,
                "--output", out,
                "--model-cache", MODEL_CACHE,
                "--tased-weights", TASED_WEIGHTS,
            ]
            env = os.environ.copy()
            env["MPLBACKEND"] = "Agg"
            env["PYTHONPATH"] = f"{SCRIPTS_DIR}:{TASED_REPO}"
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500, env=env)
            if r.returncode != 0 or not os.path.exists(out):
                JOBS[job_id] = {"status": "error", "error": (r.stderr or "no output")[-1200:]}
                return
            with open(out) as f:
                report = json.load(f)

            kpis_block = {}
            overall = 0
            try:
                sys.path.insert(0, SCRIPTS_DIR)
                from cognitive_kpis import compute_cognitive_kpis
                kpi_data = compute_cognitive_kpis(report)
                kpis_block = kpi_data.get("kpis", {})
                overall = kpi_data.get("overall", 0)
            except Exception as ke:
                print(f"KPI computation failed: {ke}")

            sal = report.get("saliency", {}).get("overlay_video")
            sal_web = None
            if sal and os.path.exists(sal):
                sal_web = sal + "_web.mp4"
                tx = subprocess.run(
                    ["ffmpeg", "-y", "-i", sal, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-movflags", "+faststart", "-an", sal_web],
                    capture_output=True, text=True,
                )
                if tx.returncode != 0 or not os.path.exists(sal_web):
                    print(f"ffmpeg transcode failed: {tx.stderr[-400:]}")
                    sal_web = sal

            judgment = assess_engagement(_sample_frames(video_path, 3))
            funnel = judgment.get("funnel_stage") or "mid"
            engagement_potential, five_kpis, organic = aggregate_engagement(kpis_block, judgment, "video", funnel)
            JOBS[job_id] = {
                "status": "done",
                "result": {
                    "verdict": report.get("diagnosis", {}),
                    "engagement_potential": engagement_potential,
                    "score": engagement_potential,
                    "organic_engagement": organic,
                    "kpis": five_kpis,
                    "kpis_overall": engagement_potential,
                    "funnel_stage": funnel,
                    "product_tier": judgment.get("product_tier"),
                    "heatmap": b64(sal_web),
                    "heatmap_type": "video/mp4",
                    "timelines": {
                        "attention": report.get("key_frames", {}).get("metadata", {}).get("score_timeline", []),
                        "audio_energy": report.get("audio", {}).get("signals", {}).get("energy_timeline", []),
                    },
                },
            }
        except Exception as e:
            JOBS[job_id] = {"status": "error", "error": str(e)}
        finally:
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception:
                    pass

    @web_app.post("/api/analyze/video-url/submit")
    async def submit_video_url(url: str = Form(...), role: str = Form("creative_director")):
        job_id = str(uuid.uuid4())
        JOBS[job_id] = {"status": "fetching"}

        def work():
            try:
                import fetch_video
                fetched = fetch_video.fetch_video(url)
                if "error" in fetched:
                    JOBS[job_id] = {"status": "error", "error": fetched.get("error")}
                    return
                _run_video(job_id, fetched["video_path"])
            except Exception as e:
                JOBS[job_id] = {"status": "error", "error": str(e)}

        threading.Thread(target=work, daemon=True).start()
        return {"job_id": job_id}

    @web_app.post("/api/analyze/image/submit")
    async def submit_image(
        file: UploadFile = File(...),
        title: str = Form(None), description: str = Form(None),
        format_type: str = Form("KV"), role: str = Form("creative_director"),
    ):
        job_id = str(uuid.uuid4())
        tmp = f"/tmp/upload_{job_id}_{file.filename}"
        with open(tmp, "wb") as f:
            f.write(await file.read())
        JOBS[job_id] = {"status": "analyzing"}
        threading.Thread(
            target=_run_image,
            args=(job_id, tmp, title, description, format_type, role),
            daemon=True,
        ).start()
        return {"job_id": job_id}

    @web_app.post("/api/analyze/video/submit")
    async def submit_video_file(file: UploadFile = File(...), role: str = Form("creative_director")):
        job_id = str(uuid.uuid4())
        tmp = f"/tmp/upload_{job_id}_{file.filename}"
        with open(tmp, "wb") as f:
            f.write(await file.read())
        threading.Thread(target=_run_video, args=(job_id, tmp), daemon=True).start()
        return {"job_id": job_id}

    @web_app.get("/api/job/{job_id}")
    async def job_status(job_id: str):
        return JOBS.get(job_id, {"status": "not_found"})

    @web_app.get("/health")
    async def health():
        return {"status": "ok"}

    return web_app
