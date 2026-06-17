"""
Role Profiles
==============

Different stakeholders need different things from the same creative
analysis. This module returns the appropriate system prompt + risk
prioritization for each role.

Four roles:
  - creative_director: visual hierarchy, composition, art direction
  - marketer: hook strength, audience fit, A/B test priorities
  - strategist: channel fit, format-appropriateness, brand consistency
  - executive: single bottom line + greenlight/revise verdict
"""


ROLE_DEFINITIONS = {
    "creative_director": {
        "display_name": "Creative Director",
        "emoji": "🎨",
        "audience_lens": (
            "You are advising a senior creative director responsible for art direction. "
            "They care about visual hierarchy, composition, attention flow, brand presence, "
            "and concrete production-level changes (move element X to position Y, increase "
            "contrast between subject and background, etc.). They do NOT want marketing-funnel "
            "language or strategic positioning advice — they want specific art-direction notes."
        ),
        "priority_kpis_image": ["hierarchy", "composition", "contrast", "white_space"],
        "priority_kpis_video": ["first_fixation", "anchor_stability", "switching_cost", "pattern_interrupt"],
        "risk_framing": "Frame risks as specific art-direction notes. Reference visual elements by position and treatment.",
        "fix_style": "Concrete production-level changes (move, resize, recolor, recompose).",
    },
    "marketer": {
        "display_name": "Marketer",
        "emoji": "📣",
        "audience_lens": (
            "You are advising a brand marketer responsible for campaign performance. "
            "They care about hook strength, message clarity, audience-creative fit, "
            "and which variants to A/B test. They want to know which findings would "
            "most likely move engagement metrics. Reference funnel implications "
            "(awareness, consideration, conversion) where relevant."
        ),
        "priority_kpis_image": ["hierarchy", "contrast", "text_balance", "composition"],
        "priority_kpis_video": ["hook", "cognitive_load", "pattern_interrupt", "first_fixation"],
        "risk_framing": "Frame risks in terms of likely engagement impact. Suggest specific A/B test variants where useful.",
        "fix_style": "Testable variant proposals — 'try version A with X, version B with Y'.",
    },
    "strategist": {
        "display_name": "Strategist / Planner",
        "emoji": "🧭",
        "audience_lens": (
            "You are advising a brand strategist or planner. They care about whether "
            "this creative fits its channel and format, whether it reinforces brand "
            "consistency, and how it compares to competitive/category norms. They want "
            "evidence-based observations they can use in planning decks, not production notes."
        ),
        "priority_kpis_image": ["composition", "contrast", "complexity", "text_balance"],
        "priority_kpis_video": ["hook", "cognitive_load", "anchor_stability", "first_fixation"],
        "risk_framing": "Frame risks in terms of channel/format fit and category benchmarks. Cite percentiles when available.",
        "fix_style": "Strategic recommendations — 'reconsider for this channel', 'aligns with category norm at percentile X'.",
    },
    "executive": {
        "display_name": "Executive",
        "emoji": "💼",
        "audience_lens": (
            "You are advising a senior executive who has 30 seconds to decide whether "
            "to greenlight, revise, or kill this creative. They want a clear bottom-line "
            "verdict with the single most important risk and a concrete decision recommendation. "
            "No jargon, no nuance — just the call."
        ),
        "priority_kpis_image": ["hierarchy", "contrast"],
        "priority_kpis_video": ["hook", "cognitive_load"],
        "risk_framing": "Lead with the single highest-priority risk. Lead with the decision recommendation.",
        "fix_style": "Greenlight / revise / kill — with one sentence of why.",
    },
}


def get_role_lens(role_key):
    """Return the role definition for a role key, or default to creative_director."""
    return ROLE_DEFINITIONS.get(role_key, ROLE_DEFINITIONS["creative_director"])


def build_role_aware_system_prompt(base_prompt, role_key, format_type="image"):
    """
    Take an existing system prompt and inject role-specific framing.
    base_prompt: the standard diagnostic prompt
    role_key: creative_director / marketer / strategist / executive
    format_type: "image" or "video" (changes which KPIs to prioritize)
    """
    role = get_role_lens(role_key)
    priority = role["priority_kpis_image"] if format_type == "image" else role["priority_kpis_video"]

    augmented = base_prompt + (
        f"\n\n--- ROLE CONTEXT ---\n"
        f"{role['audience_lens']}\n\n"
        f"Prioritize these KPIs when ranking risks: {', '.join(priority)}.\n"
        f"Risk framing: {role['risk_framing']}\n"
        f"Fix style: {role['fix_style']}\n"
    )
    return augmented


def list_roles():
    """Return list of (key, display_name, emoji) for UI."""
    return [(k, v["display_name"], v["emoji"]) for k, v in ROLE_DEFINITIONS.items()]
