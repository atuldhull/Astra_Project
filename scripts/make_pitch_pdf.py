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
def main():
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    c = rl_canvas.Canvas(str(OUT_PDF), pagesize=PAGE)
    c.setTitle("ASTRA — Pitch Deck")
    c.setAuthor("ASTRA Defence-Tech 2026")

    for slide_fn in (slide_1, slide_2, slide_3, slide_4, slide_5):
        slide_fn(c)
        c.showPage()
    c.save()

    # Report
    print(f"\n{'=' * 60}")
    print(f"Wrote: {OUT_PDF}")
    size_kb = OUT_PDF.stat().st_size / 1024
    print(f"Size:  {size_kb:.0f} KB · 5 slides · 16:9 landscape")
    print(f"\nScreenshots directory: {SCREENSHOTS_DIR}")
    expected = ["mission-boxes.png", "gradcam.png", "map.png", "alerts.png", "benchmark.png"]
    for name in expected:
        exists = (SCREENSHOTS_DIR / name).exists()
        mark = "✓" if exists else "…"
        print(f"  {mark} {name}")
    missing = [n for n in expected if not (SCREENSHOTS_DIR / n).exists()]
    if missing:
        print(f"\nDrop your screenshots with those exact filenames into the folder")
        print(f"above, then re-run this script to embed them.")
    print("=" * 60)


if __name__ == "__main__":
    main()
