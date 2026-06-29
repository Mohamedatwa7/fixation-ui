import modal
import os
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
        "yt-dlp", "anthropic", "Pillow", "scipy",
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
BENCHMARK = f"{NESTED}/benchmarks/benchmark_advert_gallery_percentiles.json"
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
- High (8-10): strong, specific, distinctive emotional hook. Mid (5-7): present but mild or generic. Low (0-4): flat, purely functional.

BRAND STRENGTH (0-10) [surfaced for all funnels]
How strongly the asset attributes to its brand and how confidently the brand shows up.
- Is the logo present and clearly placed?
- attribution_without_logo: if the logo were covered, could you still identify the brand from colour, type, and style? High = distinctive system. Low = interchangeable.
- Does colour and typography feel brand-consistent and deliberate, or approximated?
- High (8-10): unmistakable brand identity. Mid (5-7): branded but not distinctive. Low (0-4): weak or absent.

DISTINCTIVENESS (0-10) [surfaced for upper funnel]
How much the asset stands apart from the visual conventions of its product category.
- Does it look different from what competitors in this category typically produce, or is it a category cliche?
- Distinctive creative is remembered and re-engaged; generic creative is scrolled past even when competent.
- High (8-10): a distinct visual or conceptual angle. Mid (5-7): competent but conventional. Low (0-4): indistinguishable from any competitor.

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
- three_second_pass: can a cold viewer extract the core message (brand, product, benefit or offer, action) within 3 seconds? (true/false)
- biggest_blocker: the single biggest comprehension blocker (competing messages, buried hook, illegible key text), or "None".

STEP 4: ENGAGEMENT DRIVERS
- primary_engagement_driver: the single strongest reason this asset will earn engagement.
- primary_engagement_risk: the single biggest reason it may underperform.

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
        "persuasive_power": dict(judgment),
        "trust_credibility": dict(judgment),
        "message_clarity_judgment": {"three_second_pass": True, "biggest_blocker": "None"},
        "primary_engagement_driver": "Not detected",
        "primary_engagement_risk": "Not detected",
    }


def _parse_engagement_json(text):
    """Strip accidental code fences / prose and json.loads the object. Neutral on failure."""
    if not text:
        return _neutral_engagement()
    try:
        t = text.strip()
        if t.startswith("```"):
            t = t.split("```", 2)[1] if "```" in t[3:] else t.lstrip("`")
            if t.startswith("json"):
                t = t[4:]
        start = t.find("{")
        end = t.rfind("}")
        if start == -1 or end == -1:
            return _neutral_engagement()
        return json.loads(t[start:end + 1])
    except Exception as e:
        print(f"engagement JSON parse failed: {e}")
        return _neutral_engagement()


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


def assess_engagement(images):
    """Send asset image(s) to the vision LLM with the engagement prompt; parse JSON robustly.
    images: list of (media_type, base64_data). Returns the parsed judgment or a neutral default."""
    if not images:
        print("[engagement] no images supplied -> neutral default")
        return _neutral_engagement()
    print(f"[engagement] calling vision LLM with {len(images)} image(s); "
          f"ANTHROPIC_API_KEY set={bool(os.environ.get('ANTHROPIC_API_KEY'))}")
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
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        parsed = _parse_engagement_json(text)
        print(f"[engagement] OK funnel={parsed.get('funnel_stage')} "
              f"emo={parsed.get('emotional_pull', {}).get('score')} "
              f"brand={parsed.get('brand_strength', {}).get('score')} "
              f"persuasive={parsed.get('persuasive_power', {}).get('score')}")
        return parsed
    except Exception as e:
        import traceback
        print(f"[engagement] FAILED ({type(e).__name__}): {e}")
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

_FUNNEL_SELECT = {
    "upper": ["attention_capture", "emotional_pull", "brand_strength", "distinctiveness", "message_clarity"],
    "lower": ["persuasive_power", "message_clarity", "attention_capture", "trust_credibility", "brand_strength"],
    "mid": ["attention_capture", "persuasive_power", "message_clarity", "emotional_pull", "brand_strength"],
}
_FUNNEL_WEIGHTS = {
    "upper": {"attention_capture": .28, "emotional_pull": .28, "brand_strength": .18, "distinctiveness": .14, "message_clarity": .12},
    "lower": {"persuasive_power": .34, "message_clarity": .22, "attention_capture": .18, "trust_credibility": .16, "brand_strength": .10},
    "mid": {"attention_capture": .22, "persuasive_power": .22, "message_clarity": .20, "emotional_pull": .18, "brand_strength": .18},
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
        "persuasive_power": {"score": round(jscore("persuasive_power"), 1), "label": "Persuasive Power", "methodology": jreason("persuasive_power")},
        "trust_credibility": {"score": round(jscore("trust_credibility"), 1), "label": "Trust & Credibility", "methodology": jreason("trust_credibility")},
    }

    stage = funnel if funnel in _FUNNEL_SELECT else "mid"
    five = {kid: all_kpis[kid] for kid in _FUNNEL_SELECT[stage]}
    engagement_potential = round(sum(all_kpis[kid]["score"] * w for kid, w in _FUNNEL_WEIGHTS[stage].items()), 1)
    print(f"[engagement] aggregate stage={stage} measured_keys={list(measured.keys())} "
          f"attention={all_kpis['attention_capture']['score']} clarity={all_kpis['message_clarity']['score']} "
          f"-> engagement_potential={engagement_potential}")
    return engagement_potential, five


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
                benchmark_path=BENCHMARK,
                role_key=role,
            )
            overlay = report.get("saliency", {}).get("overlay_path")
            kpi_data = report.get("kpis", {})
            measured = kpi_data.get("kpis", {})
            judgment = assess_engagement([(_media_type(tmp), b64(tmp))])
            funnel = judgment.get("funnel_stage") or kpi_data.get("funnel_stage") or "mid"
            engagement_potential, five_kpis = aggregate_engagement(measured, judgment, "image", funnel)
            return {
                "verdict": report.get("diagnosis", {}),
                "engagement_potential": engagement_potential,
                "score": engagement_potential,
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
                benchmark_path=BENCHMARK,
                role_key=role,
            )
            overlay = report.get("saliency", {}).get("overlay_path")
            kpi_data = report.get("kpis", {})
            measured = kpi_data.get("kpis", {})
            judgment = assess_engagement([(_media_type(image_path), b64(image_path))])
            funnel = judgment.get("funnel_stage") or kpi_data.get("funnel_stage") or "mid"
            engagement_potential, five_kpis = aggregate_engagement(measured, judgment, "image", funnel)
            JOBS[job_id] = {
                "status": "done",
                "result": {
                    "verdict": report.get("diagnosis", {}),
                    "engagement_potential": engagement_potential,
                    "score": engagement_potential,
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
            engagement_potential, five_kpis = aggregate_engagement(kpis_block, judgment, "video", funnel)
            JOBS[job_id] = {
                "status": "done",
                "result": {
                    "verdict": report.get("diagnosis", {}),
                    "engagement_potential": engagement_potential,
                    "score": engagement_potential,
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
