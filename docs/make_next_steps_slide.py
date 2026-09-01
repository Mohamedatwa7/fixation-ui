"""Generate the F1X8 next-steps slide (16:9, noir theme, business language)
-> Downloads. Usage: python docs/make_next_steps_slide.py
"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

NOIR = RGBColor(0x0A, 0x0A, 0x0A)
WHITE = RGBColor(0xFA, 0xFA, 0xFA)
MUTED = RGBColor(0x9A, 0x9A, 0x9A)
ACCENT = RGBColor(0xE0, 0xE0, 0xE0)
GREEN = RGBColor(0x8A, 0xE1, 0xB8)
GOLD = RGBColor(0xFF, 0xC8, 0x61)

# (lead-in, body, timing) — business language, numbers where they earn their place
BULLETS = [
    ("Where we stand today:",
     "F1X8 picks the better-performing Samsung creative 85 times out of 100 — proven "
     "against our own published posts — and delivers a full verdict with a ready-to-shoot "
     "fix in minutes, not the weeks a market test takes.",
     None),
    ("Why creative choice is free money:",
     "In the FF8 pre-order campaign, two versions of the same message differed 6× in "
     "click-through (0.85% vs 0.14%). Same budget, same audience — the only difference "
     "was which creative got the push.",
     None),
    ("Switch on weekly learning.",
     "The system improves automatically as every new campaign's results come in — accuracy "
     "already climbed as its training data grew, and it only gets sharper from here.",
     "this week"),
    ("Bring video up to image-level accuracy.",
     "Most of our content is video, yet video is still scored by the older method — right "
     "~73 times out of 100 vs ~85 for images. Closing that gap upgrades scoring for the "
     "majority of what we publish.",
     "2–3 weeks"),
    ("Add paid-campaign scoring.",
     "FF8 showed a 3.5× difference in cost per engagement between sister assets ($0.13 vs "
     "$0.45). A paid-tuned score means media budget always lands on the creative that buys "
     "engagement cheapest — all we need are the ads-manager reports.",
     "as reports arrive"),
    ("Make pre-flight checks standard practice.",
     "Every KV and reel scored and revised before boosting. At hero-campaign reach (~20M "
     "views), the gap between a weak and a strong creative is roughly 140,000 engagements — "
     "decided before a single dirham is spent.",
     "immediately"),
]

ADVANTAGE = ("The advantage no one can copy: F1X8 is calibrated on Samsung's own posts and results. "
             "Every campaign it scores makes it smarter — and every point of engagement it recovers is free media.")

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
slide = prs.slides.add_slide(prs.slide_layouts[6])
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = NOIR

# Header
tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(9), Inches(0.4))
r = tb.text_frame.paragraphs[0].add_run()
r.text = "F1X8 — NEXT STEPS"
r.font.size = Pt(12); r.font.name = "Consolas"; r.font.color.rgb = MUTED

tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.62), Inches(12.1), Inches(0.6))
r = tb.text_frame.paragraphs[0].add_run()
r.text = "Better creative decisions, before the budget is spent"
r.font.size = Pt(26); r.font.bold = True; r.font.name = "Segoe UI"; r.font.color.rgb = WHITE

# Bullets
box = slide.shapes.add_textbox(Inches(0.75), Inches(1.5), Inches(11.85), Inches(5.05))
tf = box.text_frame
tf.word_wrap = True
first = True
for lead, body, timing in BULLETS:
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    first = False
    p.space_after = Pt(11)
    r1 = p.add_run()
    r1.text = "●  "
    r1.font.size = Pt(11); r1.font.color.rgb = GREEN; r1.font.name = "Segoe UI"
    r2 = p.add_run()
    r2.text = lead + "  "
    r2.font.size = Pt(13.5); r2.font.bold = True
    r2.font.name = "Segoe UI"; r2.font.color.rgb = WHITE
    r3 = p.add_run()
    r3.text = body
    r3.font.size = Pt(13); r3.font.name = "Segoe UI"; r3.font.color.rgb = ACCENT
    if timing:
        r4 = p.add_run()
        r4.text = f"   — {timing}"
        r4.font.size = Pt(12); r4.font.bold = True
        r4.font.name = "Segoe UI"; r4.font.color.rgb = GOLD

# Advantage banner
tb = slide.shapes.add_textbox(Inches(0.6), Inches(6.68), Inches(12.1), Inches(0.65))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
r = p.add_run()
r.text = ADVANTAGE
r.font.size = Pt(13.5); r.font.bold = True; r.font.name = "Segoe UI"; r.font.color.rgb = GREEN

notes = slide.notes_slide.notes_text_frame
notes.text = (
    "Number sources (if challenged): 85/100 and 73/100 = pairwise accuracy on held-out Samsung "
    "creatives (image ranker AUC 0.851; video pipeline AUC 0.731). 6x CTR = FF8 upper-funnel "
    "statics q8h8offkv 0.85% vs b8kv 0.14%. $0.13 vs $0.45 = cost per engagement, FF8 lower-funnel "
    "statics. 140K = 20M impressions x (0.9% - 0.2%) engagement rate. Weekly learning: retrain "
    "loop is built with a safety gate — a new model only ships if it beats the current one. "
    "Also in the back pocket: we tested Meta's TRIBE brain-response model on 171 of our posts — "
    "zero accuracy gain over F1X8, which is why it is not part of the stack."
)

out = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "F1X8_Next_Steps.pptx")
prs.save(out)
print("wrote", out)
