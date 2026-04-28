"""
onepager — single-page pitch PDF.

Built for procurement officers / judges to take away after a 5-min demo.
Pulls live numbers from benchmarks/*.json so the metrics on the page
are always the most recent capture.

Layout (A4 portrait, single page):
  HEADER  ASTRA v3.0 - Sovereign / On-Device / Defensible
  PILLARS three side-by-side cards
  METRICS table: mAP, latency, cascade top-1, audit chain rows
  DELTA   one-line what makes ASTRA different
  FOOTER  contact + git tag + capture timestamps
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = REPO_ROOT / "benchmarks"

# Defence-genre palette.
ACCENT = colors.HexColor("#22d3ee")     # cyan
WARN = colors.HexColor("#fb923c")        # amber
LOW = colors.HexColor("#4ade80")         # green
TEXT = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
PANEL = colors.HexColor("#f1f5f9")


def _read_bench(name: str) -> dict:
    p = BENCH_DIR / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.1f}%"


def _ms(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:.0f} ms"


def render_onepager() -> bytes:
    """Render and return the PDF bytes."""
    detector = _read_bench("detector_val.json")
    latency = _read_bench("latency.json")
    adversarial = _read_bench("adversarial_ab.json")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="ASTRA v3.0 — One-Pager",
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=22, leading=24, textColor=TEXT, spaceAfter=2)
    SUB = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=8)
    H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, leading=14, textColor=TEXT, spaceBefore=6, spaceAfter=4)
    BODY = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=12, textColor=TEXT)
    PILLAR_TITLE = ParagraphStyle("pillar_t", parent=styles["Normal"], fontSize=10, leading=12, textColor=ACCENT, spaceAfter=2)
    PILLAR_BODY = ParagraphStyle("pillar_b", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=TEXT)
    SMALL = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=MUTED)

    story: list = []

    # ── Header ────────────────────────────────────────────────────────
    story.append(Paragraph("ASTRA v3.0 <font color='#22d3ee'>· SOVEREIGN</font>", H1))
    story.append(Paragraph(
        "Defence-grade aerial recognition — runs end-to-end on a 6 GB laptop GPU, no cloud, air-gappable.",
        SUB,
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED, spaceBefore=4, spaceAfter=8))

    # ── Three pillars ────────────────────────────────────────────────
    pillars_data = [[
        Paragraph("<b>SOVEREIGN</b>", PILLAR_TITLE),
        Paragraph("<b>ON-DEVICE</b>", PILLAR_TITLE),
        Paragraph("<b>DEFENSIBLE</b>", PILLAR_TITLE),
    ], [
        Paragraph(
            "Open architecture, Indian context, no US lock-in. "
            "Air-gappable. Runs on any 6 GB GPU.",
            PILLAR_BODY,
        ),
        Paragraph(
            "Stage-1 detector + stage-2 MAR20 cascade + LLM-grounded "
            "chat — all on one laptop. Data never leaves the box.",
            PILLAR_BODY,
        ),
        Paragraph(
            "Every detection signed (Ed25519). Every action SHA-256 "
            "hash-chained. Adversarially tested with measured retention.",
            PILLAR_BODY,
        ),
    ]]
    pillars = Table(pillars_data, colWidths=[60 * mm, 60 * mm, 60 * mm])
    pillars.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.4, MUTED),
        ("LINEAFTER", (0, 0), (-2, -1), 0.4, MUTED),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(pillars)
    story.append(Spacer(1, 6 * mm))

    # ── Live metrics table ────────────────────────────────────────────
    story.append(Paragraph("Live metrics", H2))

    map50 = detector.get("map_50")
    map5095 = detector.get("map_50_95")
    p50 = latency.get("p50_ms")
    p99 = latency.get("p99_ms")
    n_lat = latency.get("n", 0)
    base_ret = adversarial.get("baseline_retention")
    hard_ret = adversarial.get("hardened_retention")

    metrics_rows = [
        ["Capability", "Metric", "Value", "Source"],
        ["Stage-1 detector (DOTA)", "mAP@0.5",
         f"{map50:.3f}" if map50 is not None else "not captured",
         "scripts/capture_detector_map.py"],
        ["Stage-1 detector (DOTA)", "mAP@0.5:0.95",
         f"{map5095:.3f}" if map5095 is not None else "not captured",
         "scripts/capture_detector_map.py"],
        ["Stage-2 cascade (MAR20)", "top-1 accuracy", "89.03%", "training/configs/astra-aircraft-v1.yaml"],
        ["Pipeline E2E latency", "p50 ingest -> alert", _ms(p50),
         f"scripts/capture_latency.py (n={n_lat})"],
        ["Pipeline E2E latency", "p99 ingest -> alert", _ms(p99), ""],
        ["Adversarial robustness", "baseline retention",
         _pct(base_ret) if base_ret is not None else "not captured",
         "scripts/adversarial_ab.py"],
        ["Adversarial robustness", "hardened retention",
         _pct(hard_ret) if hard_ret is not None else "not captured", ""],
        ["Audit chain", "primitive", "SHA-256 hash chain (Bitcoin block-header pattern)", "backend/app/services/audit.py"],
        ["Federated learning", "robustness", "FoolsGold (Fung 2020) + DP-SGD", "federated/foolsgold.py"],
    ]
    metrics_tbl = Table(metrics_rows, colWidths=[42 * mm, 38 * mm, 50 * mm, 50 * mm])
    metrics_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PANEL),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT),
        ("TEXTCOLOR", (3, 1), (3, -1), MUTED),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, MUTED),
        ("LINEBELOW", (0, 1), (-1, -2), 0.2, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(metrics_tbl)
    story.append(Spacer(1, 6 * mm))

    # ── Differentiator strip ──────────────────────────────────────────
    story.append(Paragraph("What no other product hits all of:", H2))
    delta_rows = [
        ["Capability", "Palantir Gotham", "Anduril Lattice", "TAK", "Generic CV", "ASTRA v3.0"],
        ["On-device ML inference", "—", "partial", "—", "—", "✓"],
        ["Federated learning + Sybil quarantine", "—", "—", "—", "—", "✓"],
        ["Adversarial robustness measured", "—", "—", "—", "—", "✓"],
        ["Hash-chained audit + chain anchor", "—", "partial", "—", "—", "✓"],
        ["Detection-level Ed25519 signatures", "—", "—", "—", "—", "✓"],
        ["Air-gappable, sovereign", "—", "partial", "✓", "—", "✓"],
        ["Open architecture, no US lock-in", "—", "—", "✓", "—", "✓"],
    ]
    delta_tbl = Table(delta_rows, colWidths=[58 * mm, 22 * mm, 22 * mm, 14 * mm, 22 * mm, 22 * mm])
    delta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PANEL),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("TEXTCOLOR", (-1, 0), (-1, -1), ACCENT),
        ("TEXTCOLOR", (1, 1), (-2, -1), MUTED),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, MUTED),
        ("LINEBELOW", (0, 1), (-1, -2), 0.2, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(delta_tbl)
    story.append(Spacer(1, 6 * mm))

    # ── Footer ───────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.3, color=MUTED, spaceBefore=2, spaceAfter=2))
    cap_lines = []
    if detector.get("captured_at"):
        cap_lines.append(f"detector capture: {detector['captured_at']}")
    if latency.get("captured_at"):
        cap_lines.append(f"latency capture: {latency['captured_at']}")
    cap_lines.append(f"generated: {datetime.now(timezone.utc).isoformat()}")
    story.append(Paragraph(" · ".join(cap_lines), SMALL))
    story.append(Paragraph(
        "ASTRA — sovereign defence-tech. Solo build, BMSIT&M Bengaluru. Tag <b>v3.0.0-sovereign</b>.",
        BODY,
    ))

    doc.build(story)
    return buf.getvalue()
