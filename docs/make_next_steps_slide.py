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

# (lead-in, body, timing) — how we scale F1X8 inside the company
BULLETS = [
    ("Make it part of the sign-off.",
     "Start with our own social team: no KV or reel gets boosted without its F1X8 check — "
     "a 90-second step that picks the stronger creative 85 times out of 100. One campaign, "
     "one team, prove the ritual works.",
     "this month"),
    ("Close the loop with the media team & agencies.",
     "Two-way habit: they add campaign context when briefing creatives in, and send back the "
     "ads-manager results after each flight. Every report they return makes the tool smarter — "
     "the FF8 export alone exposed a 3.5× spread in cost per engagement we can now predict.",
     "next campaign"),
    ("Onboard more Samsung accounts.",
     "Today it is tuned to one account's feed. The data to extend it — 12,500 posts from other "
     "accounts — is already exported. Each new account gets scoring calibrated to its own "
     "audience and history, same as ours.",
     "1–2 months"),
    ("Give it an owner and a scoreboard.",
     "One person in creative ops owns it; one monthly page: what we scored, what we predicted, "
     "what actually happened. Trust in the tool is built the same way the tool works — by "
     "checking predictions against results, in the open.",
     "from day one"),
    ("Train the teams that touch creative.",
     "A 30-minute session per team: how to write good campaign context (it now directly drives "
     "the In-Context score), how to read the fix brief, when to trust which number. The tool is "
     "only as scaled as the people using it.",
     "first two weeks"),
    ("Take it to regional when the scoreboard proves it.",
     "After 2–3 months of tracked predictions across multiple accounts, present it to regional "
     "HQ as a MENA-built capability — with our own campaigns as the evidence, not a demo.",
     "quarter's end"),
]

ADVANTAGE = ("Scaling logic: every team that adopts it adds campaigns; every campaign adds results; "
             "every result makes it more accurate for everyone. The earlier it spreads, the faster it compounds.")

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
r.text = "Scaling F1X8 across the company"
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
    "Number sources (if challenged): 85/100 = pairwise accuracy on held-out Samsung creatives "
    "(image ranker AUC 0.851). 3.5x cost-per-engagement spread = FF8 lower-funnel statics "
    "($0.13 vs $0.45). 12,500 posts = non-brand rows already in the calibration export. "
    "90 seconds = live image diagnostic time.\n\n"
    "Sequencing logic: bullets 1-2 cost nothing and start immediately (process + data habit). "
    "Bullet 3 needs the multi-account training pass (engineering, ~4-6 weeks). Bullets 4-5 are "
    "organizational glue that make adoption stick. Bullet 6 is the expansion play once the "
    "scoreboard carries 2-3 months of tracked predictions vs actuals.\n\n"
    "Back pocket: we tested Meta's TRIBE brain-response model on 171 of our posts — zero "
    "accuracy gain over F1X8 — which answers the 'why not the neuroscience tool' question."
)

out = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "F1X8_Next_Steps.pptx")
prs.save(out)
print("wrote", out)
