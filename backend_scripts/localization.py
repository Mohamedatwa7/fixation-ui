"""
Localization Module
====================

Translates text overlays detected in creatives and assesses
market-fit risk for MENA audiences (Arabic + Urdu).

Why this matters for Samsung MENA:
  - English-only creatives in Arabic-majority markets create
    comprehension friction
  - Mixed-script designs (English + Arabic) require careful RTL
    layout consideration
  - Urdu adds Pakistani diaspora coverage in GCC markets

This module does NOT translate brand names, product names, or
hashtags — only readable English copy that would benefit from
localization.
"""

import os
import json


def assess_localization(text_overlays_description, target_format=None):
    """
    Given Qwen's text-overlay perception output, identify text that
    should be translated and produce Arabic + Urdu versions plus a
    market-fit assessment.

    Args:
        text_overlays_description: Qwen's text-overlay description string
        target_format: KV / OOH / Banner / etc. (affects criticality)

    Returns dict with:
        - detected_text: list of extracted strings
        - translations: {"ar": [...], "ur": [...]}
        - market_fit_risk: low / medium / high
        - reasoning: why this risk level
        - localization_suggestion: actionable recommendation
    """
    from anthropic import Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}
    client = Anthropic(api_key=api_key)

    if not text_overlays_description or len(text_overlays_description) < 5:
        return {
            "detected_text": [],
            "translations": {},
            "market_fit_risk": "low",
            "reasoning": "No significant text overlays detected.",
            "localization_suggestion": None,
        }

    SYS = """You are a localization advisor for Samsung MENA marketing.

You are given a description of text/typography in a creative (KV, OOH, banner, etc.) intended for MENA markets. Your job:

1. Extract all readable English text from the description (NOT brand names, product names like 'Galaxy S25', or hashtags)
2. Translate each piece to Arabic and Urdu — natural, marketing-appropriate translations (not literal)
3. Assess market-fit risk for an Arabic-speaking audience:
   - LOW: minimal/no English text, or text is just product/brand
   - MEDIUM: English headlines present, but bilingual viewers can engage
   - HIGH: English-only with no Arabic — major comprehension friction
4. Suggest a specific localization improvement

Be practical. A single English word like "NEW" on a Samsung product KV isn't a crisis; a paragraph of English body copy is.

Output strict JSON:
{
  "detected_text": ["..."],
  "translations": {
    "ar": ["..."],
    "ur": ["..."]
  },
  "market_fit_risk": "low|medium|high",
  "reasoning": "1-2 sentence explanation",
  "localization_suggestion": "Specific actionable change, or null if low risk"
}
"""

    format_context = f"Format: {target_format}. " if target_format else ""
    user_message = (
        f"{format_context}Text overlay description:\n\n"
        f"{text_overlays_description}\n\n"
        f"Produce the localization JSON."
    )

    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1200,
            system=SYS,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip().rstrip("`").strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse failed: {e}", "_raw": raw[:500]}
    except Exception as e:
        return {"error": str(e)}
