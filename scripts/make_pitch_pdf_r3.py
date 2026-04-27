"""
Generate the ASTRA Round-3 pitch deck as a 12-slide PDF.

Reads docs/pitch-content-r2.md (Round-2 pitch is the source of truth;
R3 features get appendix slides). Renders with reportlab in the project
dark theme. No screenshots needed — the deck is text-dense by design.

Run: python scripts/make_pitch_pdf_r3.py
Output: docs/astra-pitch-r3.pdf
"""

from __future__ import annotations

from pathlib import Path
import textwrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas


SLIDE_W = 13.33 * inch
SLIDE_H = 7.5 * inch
PAGE = (SLIDE_W, SLIDE_H)

BG     = colors.HexColor("#07090d")
PANEL  = colors.HexColor("#11171f")
BORDER = colors.HexColor("#243042")
TEXT   = colors.HexColor("#e6edf6")
MUTED  = colors.HexColor("#8b9bb3")
ACCENT = colors.HexColor("#ff7a1a")
GREEN  = colors.HexColor("#4ade80")
CYAN   = colors.HexColor("#22d3ee")
RED    = colors.HexColor("#ef4444")


# Slide content tuples: (title, subtitle, bullets[], stats_dict)
SLIDES: list[dict] = [
    {
        "n": "01", "kicker": "DEFENCE-TECH EXPO 2026 · BMSIT&M",
        "title": "ASTRA",
        "subtitle": "Sovereign · Specific · Federated · Mitigated · Operational · Auditable",
        "body": [
            "Aerial Surveillance & Threat Recognition Assistant.",
            "Round 1: end-to-end on a 6 GB laptop GPU. Round 2: operational layer.",
            "Round 3: command-center polish + 22 features stacked on top.",
        ],
        "footer": "v0.3.0 · sovereign build",
    },
    {
        "n": "02", "kicker": "ROUND 3 · WHAT'S NEW",
        "title": "22 features on top of R2",
        "subtitle": "Same 6 GB laptop GPU. No cloud.",
        "body": [
            "Command Center wall · 12-tile live ops view",
            "Sidebar v2 with real-time status pills + theme toggle",
            "PGD adversarial training (real per-batch FGSM)",
            "RAG commander Q&A (Phi-3.5 + retrieval, rule-based fallback)",
            "JWT auth + role gates · Onboarding tour · CSV/JSON exports",
            "Map heatmap · Mission compare · Replay scrub · Differential privacy",
            "GitHub Actions CI · full-stack docker compose · Playwright backup video",
        ],
    },
    {
        "n": "03", "kicker": "DEMO #1",
        "title": "Stage-2 cascade — fine-grained airframe ID",
        "subtitle": "Stage-1 says 'aircraft.' Stage-2 says which one.",
        "body": [
            "MAR20 dataset · 20 military airframes · 89.03% top-1 · 99.32% top-5",
            "Drag in 02-airfield-hero.jpg → 14 dets in <2 s",
            "Cascade IDs: 6× P-3C · 2× E-8 · 2× E-3 · 2× C-130 · 1× FA-18",
            "Stage-2 model size: 3.2 MB · inference: 0.5 ms/crop",
        ],
    },
    {
        "n": "04", "kicker": "DEMO #2",
        "title": "Real-time live push",
        "subtitle": "Pins POP onto the map as the pipeline runs.",
        "body": [
            "WebSocket /ws/live · single Postgres write triggers fan-out",
            "LIVE pulse indicator on every connected operator console",
            "5s polling fallback if the socket drops — never miss a pin",
        ],
    },
    {
        "n": "05", "kicker": "DEMO #3",
        "title": "Federated learning + FoolsGold + DP",
        "subtitle": "3 bases. 0 data shared. 1 better model.",
        "body": [
            "FedAvg orchestrator + FoolsGold cosine-sim Sybil quarantine",
            "Faithful re-impl of Fung et al. RAID 2020",
            "Demo: 3 honest non-IID clients + 2 colluding label-flippers",
            "  Without FoolsGold: 0% accuracy under attack",
            "  With FoolsGold: attackers w=0.000 quarantined, honest 76% acc",
            "  Δ +76 percentage points from the defense alone",
            "R3: optional DP-SGD per-client gradient noise (Abadi 2016)",
        ],
    },
    {
        "n": "06", "kicker": "DEMO #4",
        "title": "Adversarial-aware A/B",
        "subtitle": "We measured the weakness AND the mitigation curve.",
        "body": [
            "Same image. Same ε. Two model variants.",
            "v1 baseline @ ε=0.05 (helipad): 0% retention (4 → 0 dets)",
            "v1-hardened @ ε=0.05 (helipad): 80% retention (5 → 4 dets)",
            "Δ +80 percentage points on the canonical demo image.",
            "R3: PGD adversarial training (per-batch FGSM, K=3)",
            "Honest disclosure: hardened variant is partial — full PGD is the v3+",
        ],
    },
    {
        "n": "07", "kicker": "DEMO #5",
        "title": "Phone buzzes",
        "subtitle": "Commander's phone, not commander's screen.",
        "body": [
            "Telegram bot integration · httpx · threshold-gated ≥ 0.85",
            "Markdown alert with airframe + distance + narrator text",
            "Operator drops ASTRA_BOT_TOKEN + CHAT_ID in .env. That's it.",
        ],
    },
    {
        "n": "08", "kicker": "OPERATIONAL LAYER",
        "title": "Audit · Diff · Dual-control · Q&A",
        "subtitle": "What changed in *how* operators use it.",
        "body": [
            "SHA-256 hash-chained audit · /audit/verify endpoint",
            "Mission Diff — added/removed/moved tracks across passes",
            "Dual-operator engagement — 2 distinct ops to engage; 409 on dup",
            "Commander Q&A — Phi-3.5 retrieval + rule-based fallback",
            "JWT auth · operator/commander/admin roles",
        ],
    },
    {
        "n": "09", "kicker": "ARCHITECTURE",
        "title": "5-layer sovereign stack",
        "subtitle": "Every layer ships. Nothing on a 3rd-party server.",
        "body": [
            "[01] UI · React + Vite + Tailwind + Leaflet + Recharts · 9 pages",
            "[02] API · FastAPI + Pydantic · 20+ endpoints · /ws/live",
            "[03] Pipeline · YOLO → cascade → OOD → narrator → Telegram",
            "[04] Persistence · Postgres 16 + Redis 7 · SHA-256 chain",
            "[05] Federated trust · FedAvg + FoolsGold + DP-SGD",
        ],
    },
    {
        "n": "10", "kicker": "NUMBERS",
        "title": "All in one chart",
        "subtitle": "Every number reproducible by a script in this repo.",
        "body": [
            "Stage-1 mAP@0.5 (DOTA, 8 classes): 0.515 · aircraft 0.92 · ship 0.77",
            "Stage-2 cascade top-1 (MAR20, 20 airframes): 89.03% · top-5: 99.32%",
            "GPU latency: 22 ms/frame · CPU ONNX: 36 ms · cascade overhead: +0.5 ms",
            "Adversarial v1 vs v1-hardened (helipad ε=0.05): 0% → 80%",
            "Federated under attack (without/with FoolsGold): 0% → 76% accuracy",
            "Audit chain integrity: SHA-256, 100+ rows verified ok",
            "Total model size on disk: 8.7 MB",
        ],
    },
    {
        "n": "11", "kicker": "VS COMPETITION",
        "title": "Sovereign + auditable + small + free",
        "subtitle": "We don't claim Palantir parity. We claim the right trade.",
        "body": [
            "Sovereign on a laptop:        ASTRA ✓  Palantir ✗  OSS ⚠ (training only)",
            "Fine-grained military ID:     ASTRA ✓  Palantir part. OSS ✗",
            "Federated + Sybil resistance: ASTRA ✓  Palantir ?    OSS ✗",
            "Adversarial-aware A/B:        ASTRA ✓  Palantir ?    OSS ✗",
            "Tamper-evident audit:         ASTRA ✓  Palantir part. OSS ✗",
            "Cost ongoing:                 ASTRA ₹0  Palantir ₹L/mo",
            "Time to deploy:               ASTRA 5d  Palantir mos.",
        ],
    },
    {
        "n": "12", "kicker": "CLOSE",
        "title": "Trophy material.",
        "subtitle": "Three publishable contributions. One project. Five days.",
        "body": [
            "Sovereign — runs end-to-end on a 6 GB laptop GPU.",
            "Specific — 20 fine-grained military airframes via cascade.",
            "Federated — 3 bases, FoolsGold quarantine, optional DP.",
            "Mitigated — adversarial A/B with measured retention curve.",
            "Operational — dual-control, mobile alerts, mission diff, Q&A.",
            "Auditable — SHA-256 chain · verify-on-demand.",
            "Ready — `python scripts/e2e_regression.py` returns ALL GREEN.",
        ],
    },
]

OUT = Path(__file__).resolve().parent.parent / "docs" / "astra-pitch-r3.pdf"


def fill_bg(c: rl_canvas.Canvas):
    c.setFillColor(BG)
    c.rect(0, 0, SLIDE_W, SLIDE_H, fill=1, stroke=0)


def draw_grid(c: rl_canvas.Canvas):
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.3)
    step = 40
    for x in range(0, int(SLIDE_W), step):
        c.line(x, 0, x, SLIDE_H)
    for y in range(0, int(SLIDE_H), step):
        c.line(0, y, SLIDE_W, y)


def draw_corners(c: rl_canvas.Canvas):
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2)
    s = 22
    o = 18
    # tl
    c.line(o, SLIDE_H - o, o + s, SLIDE_H - o)
    c.line(o, SLIDE_H - o, o, SLIDE_H - o - s)
    # tr
    c.line(SLIDE_W - o, SLIDE_H - o, SLIDE_W - o - s, SLIDE_H - o)
    c.line(SLIDE_W - o, SLIDE_H - o, SLIDE_W - o, SLIDE_H - o - s)
    # bl
    c.line(o, o, o + s, o)
    c.line(o, o, o, o + s)
    # br
    c.line(SLIDE_W - o, o, SLIDE_W - o - s, o)
    c.line(SLIDE_W - o, o, SLIDE_W - o, o + s)


def draw_top_strip(c: rl_canvas.Canvas, slide_n: str, kicker: str):
    c.setFillColor(PANEL)
    c.rect(40, SLIDE_H - 56, SLIDE_W - 80, 32, fill=1, stroke=0)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(54, SLIDE_H - 42, f"[{slide_n}]")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(86, SLIDE_H - 42, kicker)
    c.setFillColor(MUTED)
    c.drawRightString(SLIDE_W - 54, SLIDE_H - 42, "ASTRA · v0.3.0 · sovereign build")


def draw_slide(c: rl_canvas.Canvas, slide: dict):
    fill_bg(c)
    draw_grid(c)
    draw_corners(c)
    draw_top_strip(c, slide["n"], slide["kicker"])

    # Title
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 38)
    c.drawString(54, SLIDE_H - 130, slide["title"])

    # Subtitle
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Oblique", 13)
    c.drawString(54, SLIDE_H - 158, slide["subtitle"])

    # Underline
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1)
    c.line(54, SLIDE_H - 168, SLIDE_W - 54, SLIDE_H - 168)

    # Body bullets
    c.setFillColor(TEXT)
    c.setFont("Helvetica", 13)
    y = SLIDE_H - 200
    for line in slide["body"]:
        # word-wrap
        for sub in textwrap.wrap(line, width=110):
            c.drawString(72, y, "•  " + sub if sub == textwrap.wrap(line, width=110)[0] else "    " + sub)
            y -= 19

    # Footer
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(54, 30, slide.get("footer", "ASTRA · github.com/your-org/astra"))
    c.drawRightString(SLIDE_W - 54, 30, f"slide {slide['n']} / {len(SLIDES)}")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = rl_canvas.Canvas(str(OUT), pagesize=PAGE)
    for slide in SLIDES:
        draw_slide(c, slide)
        c.showPage()
    c.save()
    print(f"Wrote {OUT}  ({len(SLIDES)} slides)")


if __name__ == "__main__":
    main()
