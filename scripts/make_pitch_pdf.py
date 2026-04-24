"""
Generate the ASTRA pitch deck as a standalone PDF.

Produces docs/astra-pitch.pdf — a 5-slide 16:9 deck in the app's dark theme.
Uses the user's own screenshots if they exist under docs/screenshots/ with
the expected filenames; otherwise leaves the slot blank with a hint.

Run: python scripts/make_pitch_pdf.py
"""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

# ── Geometry: 16:9 slide at 1280x720 points ────────────────────────────────
SLIDE_W = 13.33 * inch
SLIDE_H = 7.5 * inch
PAGE = (SLIDE_W, SLIDE_H)

# ── Colors ─────────────────────────────────────────────────────────────────
BG         = colors.HexColor("#0a0f14")
PANEL      = colors.HexColor("#121821")
BORDER     = colors.HexColor("#23303d")
TEXT       = colors.HexColor("#e5edf4")
MUTED      = colors.HexColor("#8b9ab0")
ACCENT     = colors.HexColor("#ff7a1a")
GREEN      = colors.HexColor("#4ade80")
BLUE       = colors.HexColor("#60a5fa")
PURPLE     = colors.HexColor("#a78bfa")
RED        = colors.HexColor("#ef4444")
AMBER      = colors.HexColor("#facc15")
CYAN       = colors.HexColor("#22d3ee")

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT_PDF = Path(__file__).resolve().parent.parent / "docs" / "astra-pitch.pdf"


def fill_bg(c):
    c.setFillColor(BG)
    c.rect(0, 0, SLIDE_W, SLIDE_H, fill=1, stroke=0)


def draw_header(c, label: str):
    """Small ASTRA logo top-left + slide label top-right."""
    # Logo
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.5 * inch, SLIDE_H - 0.5 * inch, "ASTRA")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(0.5 * inch, SLIDE_H - 0.7 * inch, "Aerial Surveillance & Threat Recognition")
    # Slide label (right)
    c.setFillColor(MUTED)
    c.setFont("Courier", 9)
    c.drawRightString(SLIDE_W - 0.5 * inch, SLIDE_H - 0.5 * inch, label)


def draw_footer(c, idx: int, total: int):
    c.setFillColor(MUTED)
    c.setFont("Courier", 8)
    c.drawString(0.5 * inch, 0.3 * inch, "sovereign · explainable · measured")
    c.drawRightString(SLIDE_W - 0.5 * inch, 0.3 * inch, f"{idx} / {total}")


def panel_box(c, x, y, w, h, *, fill=PANEL, border=BORDER, border_w=0.75, radius=8):
    c.setFillColor(fill)
    c.setStrokeColor(border)
    c.setLineWidth(border_w)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def multiline_text(c, text: str, x: float, y_top: float, *, font="Helvetica", size=14, color=TEXT, leading=None):
    """Draw multi-line text top-down from y_top."""
    if leading is None:
        leading = size * 1.35
    c.setFont(font, size)
    c.setFillColor(color)
    yy = y_top
    for line in text.split("\n"):
        c.drawString(x, yy, line)
        yy -= leading
    return yy


def try_image(c, path: Path, x, y, w, h):
    """Draw image at (x,y) with size (w,h). If file missing, draw a placeholder box."""
    if path.exists():
        try:
            c.drawImage(str(path), x, y, w, h, preserveAspectRatio=True, anchor="c", mask="auto")
            return True
        except Exception:
            pass
    # Placeholder
    panel_box(c, x, y, w, h, fill=colors.HexColor("#0f1419"), border=colors.HexColor("#2a3441"))
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawCentredString(x + w / 2, y + h / 2, f"[ screenshot: {path.name} ]")
    c.setFont("Helvetica", 7)
    c.drawCentredString(x + w / 2, y + h / 2 - 14, "save your screenshot to this path")
    return False


# ────────────────────────────────────────────────────────────────────────────
# SLIDE 1 — THE PROBLEM
# ────────────────────────────────────────────────────────────────────────────
def slide_1(c):
    fill_bg(c)
    draw_header(c, "01 / 05  ·  PROBLEM")

    # Big title
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 52)
    c.drawCentredString(SLIDE_W / 2, SLIDE_H - 2.0 * inch, "The ISR Data Avalanche")

    # Subtitle
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 18)
    c.drawCentredString(SLIDE_W / 2, SLIDE_H - 2.6 * inch,
                        "India's drone + satellite imagery grows faster than analysts can review it.")

    # 4 pain-point boxes across the middle
    box_y = 3.0 * inch
    box_h = 1.6 * inch
    box_w = 2.7 * inch
    gap = 0.25 * inch
    start_x = (SLIDE_W - (4 * box_w + 3 * gap)) / 2
    pain_points = [
        ("40% /yr", "imagery growth rate", ACCENT),
        ("<20%", "frames analyzed by humans", RED),
        ("Foreign cloud", "AWS / Google / Azure — unacceptable", AMBER),
        ("Closed systems", "domestic AI = non-explainable", PURPLE),
    ]
    for i, (big, small, col) in enumerate(pain_points):
        bx = start_x + i * (box_w + gap)
        panel_box(c, bx, box_y, box_w, box_h)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(bx + box_w / 2, box_y + box_h - 0.7 * inch, big)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 12)
        c.drawCentredString(bx + box_w / 2, box_y + box_h - 1.15 * inch, small)

    # Answer line
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(SLIDE_W / 2, 1.7 * inch, "We built ASTRA.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 13)
    c.drawCentredString(SLIDE_W / 2, 1.35 * inch,
                        "Sovereign, explainable, edge-deployable AI for aerial target recognition.")

    draw_footer(c, 1, 5)


# ────────────────────────────────────────────────────────────────────────────
# SLIDE 2 — ARCHITECTURE
# ────────────────────────────────────────────────────────────────────────────
def slide_2(c):
    fill_bg(c)
    draw_header(c, "02 / 05  ·  ARCHITECTURE")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(0.75 * inch, SLIDE_H - 1.5 * inch, "Four-Layer Sovereign Stack")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 14)
    c.drawString(0.75 * inch, SLIDE_H - 1.85 * inch,
                 "Fully offline · pixel-level explainable · human-in-the-loop · robustness-tested")

    # Left: 4 stacked layer cards
    left_x = 0.75 * inch
    card_w = 7.0 * inch
    card_h = 0.95 * inch
    gap = 0.12 * inch
    top_y = SLIDE_H - 2.4 * inch

    layers = [
        ("Layer 4", "COMMAND & CONTROL",
         "6-view dashboard · Mission · Map · Alerts · Audit · Benchmark · Adversarial", ACCENT),
        ("Layer 3", "FUSION & REASONING",
         "ByteTrack · geo-ref · threat scoring · Grad-CAM explainability · narrator · PDF reports", GREEN),
        ("Layer 2", "INFERENCE",
         "YOLOv11-nano · 2.6M params · 22 ms GPU / 36 ms CPU · 5.5 MB ONNX", BLUE),
        ("Layer 1", "INGEST",
         "file upload · RTSP/HTTP stream · GPS-from-EXIF · satellite tiles", PURPLE),
    ]
    for i, (lnum, title, detail, col) in enumerate(layers):
        y = top_y - i * (card_h + gap) - card_h
        panel_box(c, left_x, y, card_w, card_h)
        # Layer number
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left_x + 15, y + card_h - 22, lnum.upper())
        # Title
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(left_x + 15, y + card_h - 48, title)
        # Detail
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(left_x + 15, y + 14, detail)

    # Right: 4 principle badges
    right_x = 8.3 * inch
    badge_w = 4.2 * inch
    badge_h = 0.85 * inch
    bgap = 0.18 * inch
    principles = [
        ("SOVEREIGN", "zero foreign API calls · air-gap ready", ACCENT),
        ("EXPLAINABLE", "Grad-CAM + natural-language narrator", GREEN),
        ("HUMAN-IN-THE-LOOP", "no autonomous engagement path", BLUE),
        ("ROBUSTNESS-TESTED", "measured adversarial weakness, exposed", RED),
    ]
    top_py = top_y - 0.1 * inch
    for i, (name, desc, col) in enumerate(principles):
        y = top_py - i * (badge_h + bgap) - badge_h
        # Background at 15% opacity of accent
        c.setFillColor(colors.HexColor("#1a222d"))
        c.setStrokeColor(col)
        c.setLineWidth(1.5)
        c.roundRect(right_x, y, badge_w, badge_h, 6, fill=1, stroke=1)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(right_x + 14, y + badge_h - 26, name)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(right_x + 14, y + 12, desc)

    draw_footer(c, 2, 5)


# ────────────────────────────────────────────────────────────────────────────
# SLIDE 3 — LIVE DEMO (screenshot grid)
# ────────────────────────────────────────────────────────────────────────────
def slide_3(c):
    fill_bg(c)
    draw_header(c, "03 / 05  ·  LIVE DEMO")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch,
                 "Upload · Detect · Explain · Geo-locate · Rank · Audit")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 12)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "Running at  http://localhost:5173  ·  sovereign, offline, no external calls")

    # 2x2 grid of screenshots
    img_w = 5.9 * inch
    img_h = 2.25 * inch
    gap = 0.25 * inch
    grid_x = (SLIDE_W - (2 * img_w + gap)) / 2
    grid_top_y = SLIDE_H - 2.0 * inch

    tiles = [
        ("mission-boxes.png", "Mission · 32 detections in 151 ms", GREEN, grid_x,                  grid_top_y - img_h),
        ("gradcam.png",       "Grad-CAM · pixel-level explainability", BLUE, grid_x + img_w + gap, grid_top_y - img_h),
        ("map.png",           "Map · real geo-coordinates, AOI box",   AMBER, grid_x,                grid_top_y - 2 * img_h - gap),
        ("alerts.png",        "Alerts · narrator + re-rankable queue", PURPLE, grid_x + img_w + gap, grid_top_y - 2 * img_h - gap),
    ]
    for fname, caption, col, x, y in tiles:
        try_image(c, SCREENSHOTS_DIR / fname, x, y, img_w, img_h)
        # Caption bar
        c.setFillColor(colors.HexColor("#0a0f14"))
        c.setStrokeColor(col)
        c.setLineWidth(1)
        cap_y = y
        cap_h = 0.35 * inch
        c.rect(x, cap_y, img_w, cap_h, fill=1, stroke=0)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 10, cap_y + 9, caption)

    draw_footer(c, 3, 5)


# ────────────────────────────────────────────────────────────────────────────
# SLIDE 4 — NUMBERS + ADVERSARIAL
# ────────────────────────────────────────────────────────────────────────────
def slide_4(c):
    fill_bg(c)
    draw_header(c, "04 / 05  ·  NUMBERS")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Measured, not marketed.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 13)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "DOTA-v1.5 held-out val · 1,561 images · 67,029 annotated objects")

    # 4 big stat cards
    card_w = 2.85 * inch
    card_h = 1.55 * inch
    gap = 0.18 * inch
    start_x = 0.75 * inch
    card_y = SLIDE_H - 3.5 * inch

    stats = [
        ("0.515",    "mAP@0.5 overall",       "across 8 classes · 0.915 on aircraft", ACCENT),
        ("22.3 ms",  "GPU latency (median)",  "RTX 4050 Laptop · 44.9 FPS",           GREEN),
        ("36 ms",    "CPU latency (median)",  "Ryzen 7 · ONNX Runtime · 28 FPS",      BLUE),
        ("5.5 MB",   "model size",            "yolo11n ONNX · Jetson-Nano-ready",     PURPLE),
    ]
    for i, (big, label, sub, col) in enumerate(stats):
        bx = start_x + i * (card_w + gap)
        panel_box(c, bx, card_y, card_w, card_h)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(bx + 12, card_y + card_h - 22, label.upper())
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 34)
        c.drawString(bx + 12, card_y + card_h - 60, big)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(bx + 12, card_y + 12, sub)

    # Adversarial degradation table (right-half below)
    adv_x = 6.7 * inch
    adv_y = 0.8 * inch
    adv_w = 6.0 * inch
    adv_h = 2.4 * inch
    panel_box(c, adv_x, adv_y, adv_w, adv_h)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(adv_x + 14, adv_y + adv_h - 25, "ADVERSARIAL ROBUSTNESS — FGSM, measured live")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(adv_x + 14, adv_y + adv_h - 42,
                 "We do not hide weakness. We measure it. Mitigation is roadmap v1.2.")

    # Table rows
    rows = [
        ("ε = 0.00",   "100% retained",      "baseline",              GREEN),
        ("ε = 0.02",   "77% retained",       "light degradation",     AMBER),
        ("ε = 0.05",   "46% retained",       "vehicle classes collapse", colors.HexColor("#fb923c")),
        ("ε = 0.12",   "catastrophic",       "false-positive bloom",  RED),
    ]
    row_y = adv_y + adv_h - 70
    for eps, pct, note, col in rows:
        c.setFillColor(TEXT)
        c.setFont("Courier-Bold", 11)
        c.drawString(adv_x + 18, row_y, eps)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(adv_x + 95, row_y, pct)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(adv_x + 240, row_y, note)
        row_y -= 24

    # Left-half below: benchmark screenshot
    try_image(c, SCREENSHOTS_DIR / "benchmark.png",
              0.75 * inch, 0.8 * inch, 5.85 * inch, 2.4 * inch)

    # Footer line
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(SLIDE_W / 2, 0.55 * inch,
                        "Trained in 1h 53m on a ₹90,000 consumer laptop. Not cloud.")

    draw_footer(c, 4, 5)


# ────────────────────────────────────────────────────────────────────────────
# SLIDE 5 — ROADMAP + CLOSE
# ────────────────────────────────────────────────────────────────────────────
def slide_5(c):
    fill_bg(c)
    draw_header(c, "05 / 05  ·  ROADMAP")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Roadmap — what ships next")

    # 4 milestone cards horizontally
    card_w = 2.85 * inch
    card_h = 1.7 * inch
    gap = 0.18 * inch
    start_x = 0.75 * inch
    card_y = SLIDE_H - 3.3 * inch

    ms = [
        ("v1.1",  "2 weeks",
         "MAR20 fine-grained military aircraft\n(Su-57, MiG-29, F-16 variants)\nrotated-bbox for bridges",
         ACCENT),
        ("v1.2",  "1 month",
         "Adversarial training\n(randomized smoothing)\nDJI telemetry → pinhole georef",
         GREEN),
        ("v2.0",  "3 months",
         "Multi-camera fusion\nmovement-intent scoring\nfederated training across bases",
         BLUE),
        ("v3.0",  "6 months",
         "Jetson Orin Nano edge deploy\nair-gapped ops\nMIL-STD-882 safety case",
         PURPLE),
    ]
    for i, (ver, t, detail, col) in enumerate(ms):
        bx = start_x + i * (card_w + gap)
        panel_box(c, bx, card_y, card_w, card_h)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(bx + 14, card_y + card_h - 32, ver)
        c.setFillColor(MUTED)
        c.setFont("Courier", 9)
        c.drawString(bx + 14, card_y + card_h - 52, t)
        # Detail multi-line
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 10)
        yy = card_y + card_h - 74
        for line in detail.split("\n"):
            c.drawString(bx + 14, yy, line)
            yy -= 14

    # Divider
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(0.75 * inch, 3.0 * inch, SLIDE_W - 0.75 * inch, 3.0 * inch)

    # HUGE closing tagline
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 58)
    c.drawCentredString(SLIDE_W / 2, 1.9 * inch,
                        "SOVEREIGN.  EXPLAINABLE.  MEASURED.  READY.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 16)
    c.drawCentredString(SLIDE_W / 2, 1.3 * inch,
                        "— ASTRA · BMSIT&M Bengaluru · Apr 30 2026 —")

    draw_footer(c, 5, 5)


# ────────────────────────────────────────────────────────────────────────────
def slide_6_divider(c):
    """Divider: APPENDIX — use if you want more slides."""
    fill_bg(c)
    draw_header(c, "A00 / A07  ·  APPENDIX")
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 68)
    c.drawCentredString(SLIDE_W / 2, SLIDE_H / 2 + 40, "APPENDIX")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 16)
    c.drawCentredString(SLIDE_W / 2, SLIDE_H / 2 - 10,
                        "Reference slides — pick any to extend the core 5 if you have more time.")
    c.drawCentredString(SLIDE_W / 2, SLIDE_H / 2 - 34,
                        "Each slide below is self-contained; use the ones a judge probes.")

    topics = [
        "A01  DATASET & TRAINING METHODOLOGY",
        "A02  FULL FEATURE INVENTORY",
        "A03  COMPARATIVE EDGE vs COMMERCIAL / DOMESTIC",
        "A04  DEFENCE USE CASES",
        "A05  DEPLOYMENT ECONOMICS",
        "A06  Q&A CHEAT SHEET",
        "A07  CREDITS & HONEST DISCLOSURES",
    ]
    y = SLIDE_H / 2 - 90
    c.setFillColor(TEXT)
    c.setFont("Courier-Bold", 13)
    for t in topics:
        c.drawCentredString(SLIDE_W / 2, y, t)
        y -= 20

    draw_footer(c, 6, 12)


def slide_7_dataset(c):
    fill_bg(c)
    draw_header(c, "A01 / A07  ·  DATASET & TRAINING")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Dataset & Training Methodology")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 13)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "Every number is measurable and reproducible from the repo.")

    # Left column: dataset
    lx = 0.75 * inch
    ly = SLIDE_H - 2.3 * inch
    panel_box(c, lx, 0.8 * inch, 6.0 * inch, ly - 0.8 * inch + inch * 0.1, radius=6)
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(lx + 14, ly - 8, "DATASET — DOTA-v1.5")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(lx + 14, ly - 28, "Wuhan University · publicly published aerial imagery benchmark")

    dataset_rows = [
        ("Source",        "Google Earth + WorldView satellite + drone captures"),
        ("Raw images",    "1,869 (train + val)"),
        ("Raw size",      "~4,000 × 4,000 px per image"),
        ("Pre-processing", "1,024² tiles with 20% overlap · OBB→AABB conversion"),
        ("Output",         "9,832 train / 1,561 val / 1,497 test tiles"),
        ("Training classes", "8 defence-relevant (filtered from DOTA's 18)"),
    ]
    yy = ly - 60
    for label, val in dataset_rows:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(lx + 14, yy, label.upper())
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 11)
        c.drawString(lx + 150, yy, val)
        yy -= 22

    # Class counts
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(lx + 14, yy - 6, "CLASSES + PER-CLASS mAP@0.5")
    classes_mAP = [
        ("aircraft-fixed-wing", 0.915, GREEN),
        ("ship",                0.770, GREEN),
        ("harbor",              0.733, GREEN),
        ("large-vehicle",       0.660, AMBER),
        ("small-vehicle",       0.408, AMBER),
        ("storage-depot",       0.393, AMBER),
        ("aircraft-rotor",      0.242, RED),
        ("bridge",              0.000, RED),
    ]
    yy -= 24
    for cname, m, col in classes_mAP:
        c.setFillColor(TEXT)
        c.setFont("Courier", 10)
        c.drawString(lx + 20, yy, cname)
        c.setFillColor(col)
        c.setFont("Courier-Bold", 10)
        c.drawRightString(lx + 260, yy, f"{m:.3f}")
        # inline bar
        bar_max = 80
        c.setStrokeColor(col)
        c.setLineWidth(3)
        c.line(lx + 270, yy + 3, lx + 270 + bar_max * m, yy + 3)
        yy -= 15

    # Right column: training
    rx = 7.0 * inch
    ry = SLIDE_H - 2.3 * inch
    rh = ry - 0.8 * inch + inch * 0.1
    panel_box(c, rx, 0.8 * inch, 5.6 * inch, rh, radius=6)
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(rx + 14, ry - 8, "TRAINING CONFIGURATION")

    train_rows = [
        ("Model",       "YOLOv11-nano"),
        ("Params",      "2.6 M"),
        ("Input size",  "640 × 640 (letterboxed)"),
        ("Epochs",      "40 · early-stop patience 10"),
        ("Batch size",  "4 (AMP · mixed precision)"),
        ("Fraction",    "0.3 (30% of tiles per epoch — fast)"),
        ("Optimizer",   "AdamW · lr0=0.001 · cos LR"),
        ("Augmentation", "mosaic · HSV · flips · rotations"),
        ("Validation",  "disabled during train (6GB VRAM)"),
        ("Hardware",    "RTX 4050 Laptop · 6 GB VRAM"),
        ("Total time",  "1 hour 53 minutes"),
        ("Export",      "PyTorch .pt → ONNX opset 17"),
    ]
    yy = ry - 32
    for label, val in train_rows:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(rx + 14, yy, label.upper())
        c.setFillColor(TEXT)
        c.setFont("Courier", 10)
        c.drawString(rx + 150, yy, val)
        yy -= 18

    draw_footer(c, 7, 12)


def slide_8_features(c):
    fill_bg(c)
    draw_header(c, "A02 / A07  ·  FEATURES")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Everything shipped — full inventory")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 13)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "6 dashboard pages · 13 API endpoints · 7 novel technical features")

    # 3-column feature grid
    col_w = 3.9 * inch
    col_h = 4.8 * inch
    gap = 0.2 * inch
    start_x = 0.75 * inch
    col_y = 0.8 * inch

    cols = [
        (
            "6  UI  PAGES", ACCENT,
            [
                ("Mission",    "upload · boxes · Grad-CAM · video playback"),
                ("Map",        "geo-pins · AOI polygon · track polylines"),
                ("Alerts",     "ranked queue · narrator · live rerank"),
                ("Audit",      "append-only log · signed PDF export"),
                ("Benchmark",  "real mAP · latency charts · model stats"),
                ("Adversarial","FGSM attack · ε slider · side-by-side"),
            ],
        ),
        (
            "13  API  ENDPOINTS", GREEN,
            [
                ("/health",             "device + model status"),
                ("/ingest",             "file upload → pipeline"),
                ("/ingest/url",         "RTSP / HTTP stream ingest"),
                ("/predict",            "one-shot inference JSON"),
                ("/explain",            "Grad-CAM PNG overlay"),
                ("/adversarial",        "FGSM + noise attack JSON"),
                ("/detections",         "filter + list detections"),
                ("/tracks",             "ByteTrack groups per mission"),
                ("/alerts",             "ranked threats"),
                ("PATCH /alerts/{id}",  "confirm / reject / escalate"),
                ("/audit",              "tamper-evident event log"),
                ("/reports/...pdf",     "SHA-256-signed mission PDF"),
                ("/ws/live",            "reserved live-push channel"),
            ],
        ),
        (
            "7  NOVEL  FEATURES", BLUE,
            [
                ("Grad-CAM / EigenCAM",  "click a box → pixel attention"),
                ("ByteTrack tracking",   "stable track IDs + trails"),
                ("FGSM adversarial",     "measured model weakness"),
                ("Alert narrator",       "commander-language summaries"),
                ("Signed PDF reports",   "SHA-256 tamper-evident"),
                ("RTSP / URL stream",    "live drone feed ingest"),
                ("EXIF-GPS auto-AOI",    "real-world coords from image"),
            ],
        ),
    ]

    for i, (title, col_color, rows) in enumerate(cols):
        x = start_x + i * (col_w + gap)
        panel_box(c, x, col_y, col_w, col_h, radius=6)
        # Title
        c.setFillColor(col_color)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 14, col_y + col_h - 24, title)
        # Rows
        yy = col_y + col_h - 50
        for name, desc in rows:
            c.setFillColor(TEXT)
            c.setFont("Courier-Bold", 9)
            c.drawString(x + 14, yy, name)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 9)
            c.drawString(x + 14, yy - 11, desc)
            yy -= 26

    draw_footer(c, 8, 12)


def slide_9_comparison(c):
    fill_bg(c)
    draw_header(c, "A03 / A07  ·  COMPARATIVE EDGE")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "ASTRA vs the alternatives")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 13)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "What makes us the right answer for Indian defence — point by point.")

    # Table
    rows = [
        ("DIMENSION",             "ASTRA",                "AWS Rekognition",   "Google Vision AI",  "Closed Domestic"),
        ("Sovereignty",           "100% offline",         "Foreign cloud",     "Foreign cloud",     "Partial"),
        ("Explainability",        "Grad-CAM + narrator",  "Black box",         "Black box",         "None"),
        ("Human-in-the-loop",     "Mandatory by design",  "Optional",          "Optional",          "Varies"),
        ("Adversarial testing",   "Measured & exposed",   "Not published",     "Not published",     "Not published"),
        ("Audit trail",           "SHA-256 signed",       "CloudTrail (theirs)","Minimal",          "Varies"),
        ("Edge deployment",       "5.5 MB · Jetson-ready","Cloud-only",        "Cloud-only",        "Varies"),
        ("Latency",               "22-36 ms local",       "~300 ms network",   "~200 ms network",   "Varies"),
        ("Cost",                  "One-time Jetson ₹30k", "$$ per inference",  "$$ per inference",  "Classified"),
        ("Air-gapped ops",        "Yes",                  "No",                "No",                "Varies"),
    ]

    col_x = [0.75 * inch, 4.1 * inch, 6.7 * inch, 9.0 * inch, 11.3 * inch]
    col_w = [3.3 * inch, 2.5 * inch, 2.25 * inch, 2.25 * inch, 2.0 * inch]
    row_h = 0.38 * inch
    top_y = SLIDE_H - 2.3 * inch

    for ri, row in enumerate(rows):
        y = top_y - ri * row_h - row_h
        if ri == 0:
            # Header
            c.setFillColor(colors.HexColor("#1a222d"))
            c.rect(0.75 * inch, y, 12.0 * inch, row_h, fill=1, stroke=0)
            c.setFillColor(ACCENT)
            c.setFont("Helvetica-Bold", 10)
            for i, cell in enumerate(row):
                c.drawString(col_x[i] + 8, y + 10, cell.upper())
        else:
            if ri % 2 == 0:
                c.setFillColor(colors.HexColor("#10151b"))
                c.rect(0.75 * inch, y, 12.0 * inch, row_h, fill=1, stroke=0)
            # First col = dimension name (white bold)
            c.setFillColor(TEXT)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(col_x[0] + 8, y + 10, row[0])
            # ASTRA col (green)
            c.setFillColor(GREEN)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(col_x[1] + 8, y + 10, row[1])
            # Others (muted)
            for i in (2, 3, 4):
                c.setFillColor(MUTED)
                c.setFont("Helvetica", 9)
                c.drawString(col_x[i] + 8, y + 10, row[i])

    # Footer takeaway
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(SLIDE_W / 2, 1.0 * inch,
                        "Four wins in one architecture: sovereign, explainable, edge-deployable, robustness-tested.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(SLIDE_W / 2, 0.75 * inch,
                        "Nobody else hits all four. That's our moat.")

    draw_footer(c, 9, 12)


def slide_10_usecases(c):
    fill_bg(c)
    draw_header(c, "A04 / A07  ·  USE CASES")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Where ASTRA actually plugs in")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 13)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "Six operational scenarios with matching classes and demonstrated capabilities.")

    # 2x3 grid of use cases
    uc_w = 4.0 * inch
    uc_h = 2.15 * inch
    gap = 0.15 * inch
    start_x = 0.75 * inch
    row_top = SLIDE_H - 2.05 * inch

    use_cases = [
        ("BORDER PATROL",       "recon + convoy tracking",
         "Small-vehicle + large-vehicle + aircraft-rotor classes.\nByteTrack stabilises IDs across frames — speed, bearing, intent.", ACCENT),
        ("MARITIME DOMAIN",     "naval vessel surveillance",
         "Ship (0.77 mAP) + harbor (0.73) classes. Multi-cam fusion\nroadmap v2 covers coastal approach patterns.", CYAN),
        ("AIRFIELD MONITOR",    "fighter/transport ID",
         "Aircraft-fixed-wing (0.92) + rotor classes. MAR20 (v1.1)\nadds Su-57 / MiG-29 / F-16 variant classification.", BLUE),
        ("CONVOY RECOGNITION",  "ground movement ops",
         "Large-vehicle class with density-scoring term for convoys.\nNarrator: 'Dense cluster formation · possible convoy.'", AMBER),
        ("INFRASTRUCTURE WATCH", "logistics + depots",
         "Storage-depot + harbor + bridge classes. Long-term delta\ntracking via mission timestamps in audit trail.", PURPLE),
        ("DRONE COUNTER-INTEL", "UAV detection at altitude",
         "Small-aircraft classes. Adversarial page preempts camouflage\n/ spoofing threats (FGSM fail-mode already measured).", RED),
    ]

    for i, (title, subtitle, desc, col) in enumerate(use_cases):
        r = i // 3
        cc = i % 3
        x = start_x + cc * (uc_w + gap)
        y = row_top - r * (uc_h + gap) - uc_h
        panel_box(c, x, y, uc_w, uc_h, radius=6)
        # Title
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x + 14, y + uc_h - 24, title)
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(x + 14, y + uc_h - 40, subtitle)
        # Desc
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 9.5)
        yy = y + uc_h - 62
        for line in desc.split("\n"):
            c.drawString(x + 14, yy, line)
            yy -= 13

    draw_footer(c, 10, 12)


def slide_11_deployment(c):
    fill_bg(c)
    draw_header(c, "A05 / A07  ·  DEPLOYMENT")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Deployment economics")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 13)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "Works on commodity hardware. Zero cloud bills. Air-gap compatible.")

    # Three deployment tiers
    tier_w = 4.0 * inch
    tier_h = 3.5 * inch
    gap = 0.15 * inch
    start_x = 0.75 * inch
    tier_y = SLIDE_H - 5.5 * inch

    tiers = [
        (
            "ANALYST WORKSTATION", "₹90k consumer laptop", GREEN,
            "Core use: back-office imagery review after a mission.",
            [
                ("Hardware",    "Any laptop with GPU (we used RTX 4050)"),
                ("Inference",   "22 ms GPU / 36 ms CPU per frame"),
                ("Throughput",  "44 FPS GPU · 28 FPS CPU"),
                ("Power",       "50-70 W under load"),
                ("Deployment",  "Existing fleet of analyst machines"),
                ("Ready today", "Yes · tested today"),
            ],
        ),
        (
            "EDGE UNIT", "₹30k per Jetson Orin Nano", ACCENT,
            "Core use: on-drone or at forward base — no cloud dependency.",
            [
                ("Hardware",    "Jetson Orin Nano 8GB (~$400)"),
                ("Model",       "5.5 MB ONNX · fits with headroom"),
                ("Inference",   "Expected ~60-80 ms / 12-15 FPS"),
                ("Power",       "7-15 W"),
                ("Deployment",  "Per-drone or per-forward-base"),
                ("Ready",       "v3.0 (6 months) · roadmap"),
            ],
        ),
        (
            "DATA CENTRE", "existing infra", BLUE,
            "Core use: batch processing of archived surveillance footage.",
            [
                ("Hardware",    "Any existing GPU server (RTX 3090+)"),
                ("Model",       "Same ONNX · runs via Triton / ORT"),
                ("Inference",   "5-10 ms on 3090 · 200+ FPS"),
                ("Deployment",  "Docker Compose (already shipped)"),
                ("Bill",        "Zero cloud. Own compute only."),
                ("Ready",       "Today"),
            ],
        ),
    ]

    for i, (title, subtitle, col, desc, rows) in enumerate(tiers):
        x = start_x + i * (tier_w + gap)
        panel_box(c, x, tier_y, tier_w, tier_h, radius=6)
        c.setFillColor(col)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 14, tier_y + tier_h - 26, title)
        c.setFillColor(MUTED)
        c.setFont("Courier", 10)
        c.drawString(x + 14, tier_y + tier_h - 44, subtitle)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(x + 14, tier_y + tier_h - 62, desc)
        yy = tier_y + tier_h - 85
        for label, val in rows:
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 8)
            c.drawString(x + 14, yy, label.upper())
            c.setFillColor(TEXT)
            c.setFont("Helvetica", 9)
            c.drawString(x + 92, yy, val)
            yy -= 18

    # Bottom line
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(SLIDE_W / 2, 0.9 * inch,
                        "Total lifetime cost of a cloud AI subscription > purchase of 100 Jetson edge units.")

    draw_footer(c, 11, 12)


def slide_12_qa(c):
    fill_bg(c)
    draw_header(c, "A06 / A07  ·  Q&A PREP")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Q&A cheat sheet — the 6 questions that will come up")

    qa = [
        (
            "Why is your mAP only 0.515? That's below state of the art.",
            "yolo11-nano, 2.6M params, 2 hours on a 6GB laptop. Same architecture on RTX 4090 with full DOTA + 80 epochs hits ~0.65. "
            "Our config is edge-deployable by design — drones run on Jetson, not 4090s. Aircraft class is 0.915.",
        ),
        (
            "What about adversarial attacks / camouflage?",
            "We have a dedicated Adversarial page — FGSM with real gradients, live slider. ε=0.05 drops detection 54%. "
            "We MEASURE our weakness, we don't hide it. Roadmap v1.2 adds adversarial training + randomized smoothing.",
        ),
        (
            "What's novel? Isn't this just YOLO on DOTA?",
            "Three novelties: (1) FGSM attack as a first-class UI feature for defence IDS — not a paper footnote. "
            "(2) Grad-CAM + natural-language narrator paired: pixel AND language explanation per alert. "
            "(3) Slider-based commander-directed threat scoring with full audit of weight changes.",
        ),
        (
            "How does this handle classified data?",
            "Designed sovereign — air-gapped deployment supported. Training used DOTA (public academic data). "
            "Operational training data would be the deploying agency's own labeled imagery. Federated training across bases is v2.0.",
        ),
        (
            "CPU-only machine? GPU not available?",
            "36 ms/frame on Ryzen 7 via ONNX Runtime — 28 FPS. Analyst workflows without GPU run fine. "
            "That's enough for real-time analyst review; batch pipelines scale beyond that on server-class CPUs.",
        ),
        (
            "Cost to deploy to a real defence unit?",
            "Zero cloud bill forever. ₹30-40k one-time Jetson Orin Nano per edge unit. Software is AGPL-licensed. "
            "Compare commercial AI-as-a-service — you pay per inference every day you operate.",
        ),
    ]

    y = SLIDE_H - 1.9 * inch
    for q, a in qa:
        panel_box(c, 0.75 * inch, y - 0.85 * inch, 12.0 * inch, 0.80 * inch, radius=4)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(0.9 * inch, y - 0.2 * inch, "Q: " + q)
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 9.5)
        # Wrap long answers
        line_max = 175
        words = a.split()
        cur = ""
        yy = y - 0.4 * inch
        for w in words:
            test = cur + (" " if cur else "") + w
            if c.stringWidth(test, "Helvetica", 9.5) > 11.5 * inch:
                c.drawString(1.15 * inch, yy, cur)
                cur = w
                yy -= 13
            else:
                cur = test
        if cur:
            c.drawString(1.15 * inch, yy, cur)
        y -= 1.0 * inch

    draw_footer(c, 12, 12)


def slide_13_credits(c):
    fill_bg(c)
    draw_header(c, "A07 / A07  ·  CREDITS & LIMITATIONS")

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(0.75 * inch, SLIDE_H - 1.3 * inch, "Credits & honest disclosures")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 13)
    c.drawString(0.75 * inch, SLIDE_H - 1.65 * inch,
                 "Attribution, open-source stack, and what we explicitly do NOT claim.")

    # Left: credits
    lx = 0.75 * inch
    panel_box(c, lx, 0.9 * inch, 6.0 * inch, SLIDE_H - 1.9 * inch - 0.9 * inch, radius=6)
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(lx + 14, SLIDE_H - 2.2 * inch, "CREDITS & UPSTREAM")
    rows = [
        ("Detection model",    "YOLOv11  (Ultralytics, AGPLv3)"),
        ("Training data",      "DOTA-v1.5  (Xia et al. · Wuhan Univ.)"),
        ("Tracker",            "ByteTrack  (Zhang et al. 2022)"),
        ("Explainability",     "EigenCAM  (Muhammad & Yeasin 2020)"),
        ("Attack",             "FGSM  (Goodfellow et al. 2015)"),
        ("Maps",               "Leaflet + OpenStreetMap tiles"),
        ("PDF",                "reportlab  (open source)"),
        ("Backend stack",      "FastAPI · SQLAlchemy · Postgres · Redis"),
        ("Frontend stack",     "React · Vite · Tailwind · Recharts"),
        ("Runtime",            "PyTorch 2.6 + CUDA 12.4 · ONNX Runtime"),
    ]
    yy = SLIDE_H - 2.45 * inch
    for label, val in rows:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(lx + 14, yy, label.upper())
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 10)
        c.drawString(lx + 140, yy, val)
        yy -= 20

    # Right: limitations
    rx = 7.0 * inch
    panel_box(c, rx, 0.9 * inch, 5.6 * inch, SLIDE_H - 1.9 * inch - 0.9 * inch, radius=6)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(rx + 14, SLIDE_H - 2.2 * inch, "HONEST DISCLOSURES")

    limits = [
        "Hackathon build — NOT a cleared product.",
        "Trained on public academic data; never touched classified imagery.",
        "mAP 0.515 reflects nano-model + limited training budget. RTX 4090 + full DOTA would push to ~0.65.",
        "Bridge class broken (0.00 mAP) due to OBB→AABB conversion. Roadmap v1.1 fix: rotated-bbox support.",
        "Adversarial weakness measured (ε=0.05 → 54% drop). Mitigation: roadmap v1.2 adversarial training.",
        "Single-node today. Federated training across bases is v2.0.",
        "Productionization requires: operational data validation, MIL-STD-882 safety case, drone-platform integration testing, Jetson deployment benchmarks, network-partition hardening.",
    ]
    yy = SLIDE_H - 2.5 * inch
    c.setFillColor(TEXT)
    c.setFont("Helvetica", 10)
    for line in limits:
        words = line.split()
        cur = "•  "
        for w in words:
            test = cur + " " + w if cur.strip() != "•" else cur + w
            if c.stringWidth(test, "Helvetica", 10) > 5.2 * inch:
                c.drawString(rx + 14, yy, cur)
                cur = "    " + w
                yy -= 14
            else:
                cur = test
        if cur.strip():
            c.drawString(rx + 14, yy, cur)
            yy -= 20

    # Footer
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(SLIDE_W / 2, 0.6 * inch,
                        "We tell the truth about what works and what doesn't. That's the point.")

    draw_footer(c, 13, 13)


def main():
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    c = rl_canvas.Canvas(str(OUT_PDF), pagesize=PAGE)
    c.setTitle("ASTRA — Pitch Deck")
    c.setAuthor("ASTRA Defence-Tech 2026")

    slides = [
        slide_1, slide_2, slide_3, slide_4, slide_5,
        slide_6_divider,
        slide_7_dataset, slide_8_features, slide_9_comparison,
        slide_10_usecases, slide_11_deployment, slide_12_qa, slide_13_credits,
    ]
    for fn in slides:
        fn(c)
        c.showPage()
    c.save()

    # Report
    n_slides = len(slides)
    print(f"\n{'=' * 60}")
    print(f"Wrote: {OUT_PDF}")
    size_kb = OUT_PDF.stat().st_size / 1024
    print(f"Size:  {size_kb:.0f} KB  ·  {n_slides} slides  ·  16:9 landscape")
    print(f"\nDeck structure:")
    print(f"  CORE (1-5):      problem · architecture · demo · numbers · close")
    print(f"  APPENDIX (6-13): divider · dataset · features · comparison ·")
    print(f"                    use cases · deployment · Q&A · credits")
    print(f"\nScreenshots directory: {SCREENSHOTS_DIR}")
    expected = ["mission-boxes.png", "gradcam.png", "map.png", "alerts.png", "benchmark.png"]
    for name in expected:
        exists = (SCREENSHOTS_DIR / name).exists()
        mark = "OK " if exists else "-- "
        print(f"  {mark}{name}")
    missing = [n for n in expected if not (SCREENSHOTS_DIR / n).exists()]
    if missing:
        print(f"\nDrop your screenshots with those exact filenames into the folder")
        print(f"above, then re-run this script to embed them.")
    print("=" * 60)


if __name__ == "__main__":
    main()
