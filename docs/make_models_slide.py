"""Slide 2 for the stakeholder deck: the F1X8 AI models explained simply.
Matches the Samsung-internal light deck design (white bg, black section bars,
navy titles, blue/green/orange accents). -> Downloads/F1X8_Models_Slide.pptx
"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

NAVY = RGBColor(0x1A, 0x1A, 0x2E)     # title / body text
GRAY = RGBColor(0x59, 0x59, 0x59)     # subtitle
LINE = RGBColor(0xBF, 0xBF, 0xBF)     # hairlines / box borders
BLACK = RGBColor(0x00, 0x00, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE = RGBColor(0x2F, 0x4B, 0xE0)     # keyword emphasis
GREEN = RGBColor(0x1E, 0x9E, 0x4A)    # positive metrics
ORANGE = RGBColor(0xE8, 0x86, 0x2B)   # process accents

# (header, [(text, color, bold), ...] body sentence parts, "powers" line)
CARDS = [
    ("Attention Mapping",
     [("Predicts where human eyes go in the first seconds of viewing. Trained on ", NAVY, False),
      ("200K+ real eye-tracking recordings", BLUE, True),
      (" from people watching real content.", NAVY, False)],
     "Powers: Heatmaps · attention KPIs"),
    ("Visual Understanding",
     [("An AI that ", NAVY, False),
      ("describes what is actually in the creative", BLUE, True),
      (" — products, faces, text, scenes — the way a human viewer would see it.", NAVY, False)],
     "Powers: Risks · suggested fixes"),
    ("Audio Analysis",
     [("Listens to video sound: ", NAVY, False),
      ("transcribes every spoken word", BLUE, True),
      (" and tracks music energy second by second to check sound and visuals work together.", NAVY, False)],
     "Powers: Video KPI scoring"),
    ("Design Measurement",
     [("Objective measurements of the layout — hierarchy, contrast, white space, clutter — ", NAVY, False),
      ("benchmarked against 30K real ads", BLUE, True),
      (", so every score has a percentile behind it.", NAVY, False)],
     "Powers: KPI scores · benchmarks"),
    ("Creative Judge",
     [("A senior-creative-director AI that scores what can't be measured — emotion, brand strength, distinctiveness — ", NAVY, False),
      ("following the Samsung Brand Playbook", BLUE, True),
      (".", NAVY, False)],
     "Powers: Verdict · KPI scores · fixes"),
    ("Performance Ranker",
     [("Fine-tuned on ", NAVY, False),
      ("our own posts and their real results", BLUE, True),
      (". Picks the better-performing creative ", NAVY, False),
      ("85 times out of 100", GREEN, True),
      (".", NAVY, False)],
     "Powers: Performance score · rankings"),
]

FOOTER_PARTS = [
    ("Every output on the previous slide traces back to one of these six engines — ", NAVY, False),
    ("measured and validated, not guessed", BLUE, True),
    (".", NAVY, False),
]

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
slide = prs.slides.add_slide(prs.slide_layouts[6])
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = WHITE


def runs_para(p, parts, size, font="Segoe UI"):
    for text, color, bold in parts:
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.name = font
        r.font.color.rgb = color


# Title + subtitle + hairline (matches "F1X8 Model: ..." style)
tb = slide.shapes.add_textbox(Inches(0.45), Inches(0.28), Inches(12.4), Inches(0.55))
p = tb.text_frame.paragraphs[0]
runs_para(p, [("F1X8 AI Models: What Measures What", NAVY, True)], 26)

ln = slide.shapes.add_shape(1, Inches(0.45), Inches(0.92), Inches(12.45), Emu(9525))
ln.fill.solid(); ln.fill.fore_color.rgb = LINE; ln.line.fill.background()

tb = slide.shapes.add_textbox(Inches(0.45), Inches(0.98), Inches(12.4), Inches(0.4))
p = tb.text_frame.paragraphs[0]
runs_para(p, [("The six engines behind the diagnosis — and which part of the output each one produces",
               GRAY, False)], 13)

# Card grid: 3 columns x 2 rows
COLS, ROWS = 3, 2
LEFT, TOP = Inches(0.45), Inches(1.55)
CARD_W, CARD_H = Inches(4.02), Inches(2.42)
GAP_X, GAP_Y = Inches(0.20), Inches(0.24)
BAR_H = Inches(0.36)

for i, (header, body_parts, powers) in enumerate(CARDS):
    cx = Emu(int(LEFT) + (i % COLS) * (int(CARD_W) + int(GAP_X)))
    cy = Emu(int(TOP) + (i // COLS) * (int(CARD_H) + int(GAP_Y)))

    # black header bar
    bar = slide.shapes.add_shape(1, cx, cy, CARD_W, BAR_H)
    bar.fill.solid(); bar.fill.fore_color.rgb = BLACK
    bar.line.fill.background()
    tf = bar.text_frame
    tf.margin_left = Emu(91440); tf.margin_top = Emu(18288); tf.margin_bottom = Emu(18288)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    runs_para(p, [(header, WHITE, True)], 13)

    # white body box with thin border
    body = slide.shapes.add_shape(1, cx, Emu(int(cy) + int(BAR_H)), CARD_W,
                                  Emu(int(CARD_H) - int(BAR_H)))
    body.fill.solid(); body.fill.fore_color.rgb = WHITE
    body.line.color.rgb = LINE; body.line.width = Emu(9525)
    body.shadow.inherit = False
    tf = body.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Emu(118872); tf.margin_right = Emu(118872); tf.margin_top = Emu(91440)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    runs_para(p, body_parts, 11.5)
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.LEFT
    p2.space_before = Pt(8)
    runs_para(p2, [("→ ", ORANGE, True), (powers, ORANGE, True)], 10.5)

# Footer line
tb = slide.shapes.add_textbox(Inches(0.45), Inches(6.85), Inches(12.45), Inches(0.4))
p = tb.text_frame.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
runs_para(p, FOOTER_PARTS, 13)

notes = slide.notes_slide.notes_text_frame
notes.text = (
    "Talk track: slide 1 showed the workflow (input -> AI models -> outputs). This slide opens the "
    "AI-models box. Six engines, each with one job: Attention Mapping = TASED-Net trained on real "
    "human eye-tracking (the heatmaps); Visual Understanding = Qwen vision model (what's in the "
    "frame); Audio Analysis = Whisper transcription + sound-energy tracking; Design Measurement = "
    "computer-vision metrics benchmarked on 30K ads (MAdVerse); Creative Judge = Claude scoring "
    "the human dimensions under the Samsung Brand Playbook; Performance Ranker = LoRA model "
    "fine-tuned on our own engagement results (85/100 = 0.851 AUC on held-out creatives — links "
    "to the 74%->85% accuracy story on the next slide). Orange 'Powers' lines map each engine to "
    "the Diagnosis & Output column stakeholders saw on slide 1."
)

out = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "F1X8_Models_Slide.pptx")
prs.save(out)
print("wrote", out)
