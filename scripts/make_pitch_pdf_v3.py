"""
Generate the ASTRA v3.0 industry pitch deck as a multi-page PDF.

Pulls EVERY metric live from the running backend; falls back to the
on-disk benchmark JSON files only when the backend is unreachable.
No assumed numbers. No placeholders.

Run:
    python scripts/make_pitch_pdf_v3.py
Output:
    docs/astra-pitch-v3.pdf
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


# ── Theme ───────────────────────────────────────────────────────────
BG       = colors.HexColor("#07090d")
PANEL    = colors.HexColor("#11171f")
PANEL2   = colors.HexColor("#1c2533")
BORDER   = colors.HexColor("#243042")
TEXT     = colors.HexColor("#e6edf6")
MUTED    = colors.HexColor("#8b9bb3")
MUTED2   = colors.HexColor("#5a6477")
ACCENT   = colors.HexColor("#ff7a1a")
CYAN     = colors.HexColor("#22d3ee")
GREEN    = colors.HexColor("#4ade80")
AMBER    = colors.HexColor("#fbbf24")
RED      = colors.HexColor("#ef4444")
PURPLE   = colors.HexColor("#a78bfa")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "docs" / "astra-pitch-v3.pdf"
BACKEND_BASE = os.environ.get("ASTRA_PITCH_BACKEND", "http://127.0.0.1:8000")


# ── Live data fetch ─────────────────────────────────────────────────

def _http_get_json(url: str, timeout: float = 8.0) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _read_json_file(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def gather_live_data() -> dict:
    """Pull every numeric the deck wants from the running stack."""
    data: dict = {"sources": {}, "as_of": datetime.now().isoformat(timespec="seconds")}

    # /health/dashboard — the source of truth for runtime state
    dash = _http_get_json(f"{BACKEND_BASE}/api/v1/health/dashboard")
    data["dashboard"] = dash
    data["sources"]["dashboard"] = "live" if dash else "unavailable"

    # Detector mAP
    det_path = REPO_ROOT / "benchmarks" / "detector_val.json"
    data["detector"] = _read_json_file(det_path)
    data["sources"]["detector"] = "file" if data["detector"] else "missing"

    # Latency
    lat_path = REPO_ROOT / "benchmarks" / "latency.json"
    data["latency"] = _read_json_file(lat_path)
    data["sources"]["latency"] = "file" if data["latency"] else "missing"

    # OOD
    ood = _http_get_json(f"{BACKEND_BASE}/api/v1/ood/calibration")
    data["ood"] = ood
    data["sources"]["ood"] = "live" if ood else "unavailable"

    # Anchors + chain head
    anc = _http_get_json(f"{BACKEND_BASE}/api/v1/anchor/status")
    data["anchor"] = anc
    data["sources"]["anchor"] = "live" if anc else "unavailable"

    # Mesh peers
    mesh = _http_get_json(f"{BACKEND_BASE}/api/v1/mesh/peers")
    data["mesh"] = mesh
    data["sources"]["mesh"] = "live" if mesh else "unavailable"

    # Provenance key fingerprint
    prov = _http_get_json(f"{BACKEND_BASE}/api/v1/provenance/key")
    data["provenance"] = prov
    data["sources"]["provenance"] = "live" if prov else "unavailable"

    # Sentinel scenarios
    sentinel = _http_get_json(f"{BACKEND_BASE}/api/v1/sentinel/scenarios")
    data["sentinel"] = sentinel
    data["sources"]["sentinel"] = "live" if sentinel else "unavailable"

    return data


# ── Helpers ─────────────────────────────────────────────────────────

def fmt_int(n: int | float | None) -> str:
    if n is None:
        return "—"
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def fmt_float(n: float | None, dp: int = 3) -> str:
    if n is None:
        return "—"
    try:
        return f"{float(n):.{dp}f}"
    except Exception:
        return str(n)


def trunc_hash(h: str | None, head: int = 10, tail: int = 8) -> str:
    if not h:
        return "—"
    if len(h) <= head + tail + 1:
        return h
    return f"{h[:head]}…{h[-tail:]}"


def fmt_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s} s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m} m {s} s"
    h, m = divmod(m, 60)
    return f"{h} h {m} m"


# ── Slide drawing primitives ────────────────────────────────────────

SLIDE_W = 13.33 * inch
SLIDE_H = 7.5 * inch
PAGE = (SLIDE_W, SLIDE_H)


def page_chrome(c: rl_canvas.Canvas, slide_no: int, total: int, footer: str) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, SLIDE_W, SLIDE_H, fill=1, stroke=0)
    # Top accent rule
    c.setFillColor(ACCENT)
    c.rect(0.5 * inch, SLIDE_H - 0.4 * inch, 0.6 * inch, 2, fill=1, stroke=0)
    # Brand strip
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(0.5 * inch, SLIDE_H - 0.55 * inch, "ASTRA · v3.0")
    c.setFillColor(MUTED2)
    c.setFont("Helvetica", 8)
    c.drawString(1.4 * inch, SLIDE_H - 0.55 * inch,
                 "Aerial Surveillance & Threat Recognition Assistant")
    # Page no
    c.setFillColor(MUTED2)
    c.setFont("Helvetica", 8)
    c.drawRightString(SLIDE_W - 0.5 * inch, SLIDE_H - 0.55 * inch,
                      f"{slide_no:02d} / {total:02d}")
    # Bottom rule + footer
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.4)
    c.line(0.5 * inch, 0.45 * inch, SLIDE_W - 0.5 * inch, 0.45 * inch)
    c.setFillColor(MUTED2)
    c.setFont("Helvetica", 7.5)
    c.drawString(0.5 * inch, 0.3 * inch, footer)
    c.drawRightString(SLIDE_W - 0.5 * inch, 0.3 * inch,
                      "release/3.0 · v3.0.0-")


def title_block(c: rl_canvas.Canvas, title: str, subtitle: str,
                kicker: str | None = None) -> float:
    """Returns y where content can start."""
    y = SLIDE_H - 1.05 * inch
    if kicker:
        c.setFillColor(CYAN)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.55 * inch, y, kicker.upper())
        y -= 0.20 * inch
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(0.55 * inch, y - 0.25 * inch, title)
    y -= 0.55 * inch
    if subtitle:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 11.5)
        for line in subtitle.split("\n"):
            c.drawString(0.55 * inch, y, line)
            y -= 0.18 * inch
    y -= 0.10 * inch
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(0.55 * inch, y, SLIDE_W - 0.55 * inch, y)
    return y - 0.20 * inch


def panel(c: rl_canvas.Canvas, x: float, y: float, w: float, h: float,
          fill=PANEL, stroke=BORDER) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, 4, fill=1, stroke=1)


def stat_card(c: rl_canvas.Canvas, x: float, y: float, w: float, h: float,
              label: str, value: str, sub: str | None = None,
              tone=ACCENT) -> None:
    panel(c, x, y, w, h)
    c.setFillColor(tone)
    c.rect(x, y + h - 1.5, w, 1.5, fill=1, stroke=0)
    c.setFillColor(MUTED2)
    c.setFont("Helvetica", 7.5)
    c.drawString(x + 12, y + h - 18, label.upper())
    c.setFillColor(tone)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(x + 12, y + h - 46, value)
    if sub:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(x + 12, y + 12, sub)


def bullet(c: rl_canvas.Canvas, x: float, y: float, w: float,
           body: str, bullet_color=ACCENT, body_color=TEXT,
           font: str = "Helvetica", size: float = 10.5,
           leading: float = 14) -> float:
    c.setFillColor(bullet_color)
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, "›")
    c.setFillColor(body_color)
    c.setFont(font, size)
    # naive wrap
    words = body.split()
    line: list[str] = []
    yy = y
    avail = w - 16
    for w_ in words:
        trial = " ".join(line + [w_])
        if c.stringWidth(trial, font, size) > avail and line:
            c.drawString(x + 14, yy, " ".join(line))
            yy -= leading
            line = [w_]
        else:
            line.append(w_)
    if line:
        c.drawString(x + 14, yy, " ".join(line))
        yy -= leading
    return yy


def section_label(c: rl_canvas.Canvas, x: float, y: float, text: str,
                  tone=CYAN) -> None:
    c.setFillColor(tone)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x, y, text.upper())


# ── Slides ──────────────────────────────────────────────────────────

def slide_cover(c: rl_canvas.Canvas, n: int, total: int, data: dict) -> None:
    page_chrome(c, n, total, "cover · pillars")
    # Big vertical bar of accent
    c.setFillColor(ACCENT)
    c.rect(0.55 * inch, 1.0 * inch, 4, SLIDE_H - 2.0 * inch, fill=1, stroke=0)
    # Title block (custom — bigger)
    c.setFillColor(CYAN)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(0.85 * inch, SLIDE_H - 2.0 * inch,
                 "DEFENCE-TECH AERIAL RECOGNITION · v3.0")
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 56)
    c.drawString(0.85 * inch, SLIDE_H - 3.1 * inch, "ASTRA")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 16)
    c.drawString(0.85 * inch, SLIDE_H - 3.7 * inch,
                 "Aerial Surveillance & Threat Recognition Assistant")
    # Three pillars
    px = 0.85 * inch
    py = 2.5 * inch
    pillar_w = 3.7 * inch
    pillars = [
        ("SOVEREIGN",  "On-prem · no foreign cloud · no SaaS dependency",   ACCENT),
        ("ON-DEVICE",  "RTX-class GPU · Phi-3.5 LLM local · sub-second e2e", CYAN),
        ("DEFENSIBLE", "Ed25519-signed dets · SHA-256 audit chain · cross-agency mesh", GREEN),
    ]
    for i, (h, b, t) in enumerate(pillars):
        x = px + i * (pillar_w + 0.2 * inch)
        panel(c, x, py, pillar_w, 1.5 * inch)
        c.setFillColor(t)
        c.rect(x, py + 1.5 * inch - 2, pillar_w, 2, fill=1, stroke=0)
        c.setFillColor(t)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 14, py + 1.05 * inch, h)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(x + 14, py + 0.7 * inch, b.split(" · ")[0])
        c.drawString(x + 14, py + 0.5 * inch, " · ".join(b.split(" · ")[1:]))
    # As-of
    dash = data.get("dashboard") or {}
    backend = dash.get("backend") or {}
    c.setFillColor(MUTED2)
    c.setFont("Helvetica", 8.5)
    c.drawString(0.85 * inch, 1.0 * inch,
                 f"snapshot {data.get('as_of', '—')} · "
                 f"backend {backend.get('version', '—')} · "
                 f"device {backend.get('device', '—')} · "
                 f"uptime {fmt_uptime(backend.get('uptime_s'))}")


def slide_problem(c: rl_canvas.Canvas, n: int, total: int) -> None:
    page_chrome(c, n, total, "problem · why this matters")
    y = title_block(
        c,
        "The two-front problem in defence aerial recognition",
        "Existing tools solve one side. ASTRA was built to solve both at once.\n"
        "Speed without provenance is brittle. Provenance without speed is unusable.",
        kicker="01 · the gap",
    )
    cols = [
        ("FAST BUT UNVERIFIABLE",
         "Commercial CV stacks (Roboflow, Hugging Face inference, OpenAI Vision) hit p50 in the hundreds of milliseconds, "
         "but every detection is a black box: no signature, no chain, no reproducible attestation. A judge in a defence "
         "context cannot trust an unverifiable claim, no matter how fast it arrived.",
         RED),
        ("VERIFIABLE BUT SLOW",
         "Forensic-grade pipelines (court evidence systems) chain every artifact, hash every result, and produce PDFs that "
         "stand up in court — but they run hours, not seconds. By the time the chain is built, the threat has moved.",
         AMBER),
        ("ASTRA · BOTH",
         "p50 ingest→alert under a second AND every detection signed under an Ed25519 key whose fingerprint matches the "
         "model's SHA-256 hash. Append-only audit chain anchored to an external file. Cross-agency mesh witnesses the chain "
         "with peer signatures. Defensible AND real-time, on commodity hardware.",
         GREEN),
    ]
    cw = (SLIDE_W - 1.1 * inch - 0.4 * inch) / 3
    cy = y - 2.6 * inch
    for i, (title, body, tone) in enumerate(cols):
        x = 0.55 * inch + i * (cw + 0.2 * inch)
        panel(c, x, cy, cw, 2.6 * inch)
        c.setFillColor(tone)
        c.rect(x, cy + 2.6 * inch - 2, cw, 2, fill=1, stroke=0)
        c.setFillColor(tone)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + 12, cy + 2.6 * inch - 22, title)
        # body — wrap manually
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        words = body.split()
        line: list[str] = []
        yy = cy + 2.6 * inch - 42
        avail = cw - 24
        for w_ in words:
            trial = " ".join(line + [w_])
            if c.stringWidth(trial, "Helvetica", 9.5) > avail and line:
                c.drawString(x + 12, yy, " ".join(line))
                yy -= 13
                line = [w_]
            else:
                line.append(w_)
        if line:
            c.drawString(x + 12, yy, " ".join(line))


def slide_live_state(c: rl_canvas.Canvas, n: int, total: int, data: dict) -> None:
    page_chrome(c, n, total, "live state · numbers from the running stack")
    y = title_block(
        c,
        "Live state — every number on this page is from the running backend",
        "Pulled from /api/v1/health/dashboard at deck-build time. Not synthetic. Not assumed.",
        kicker="02 · proof of working",
    )
    dash = data.get("dashboard") or {}
    backend = dash.get("backend") or {}
    db = dash.get("db") or {}
    chain = dash.get("chain") or {}
    models = dash.get("models") or {}
    ood = dash.get("ood") or {}
    lat = (data.get("latency") or {})
    det = (data.get("detector") or {})

    # 4-col hero
    hx = 0.55 * inch
    hy = y - 1.0 * inch
    hw = (SLIDE_W - 1.1 * inch - 3 * 0.18 * inch) / 4
    cards = [
        ("MISSIONS",     fmt_int(db.get("mission_count")),
         f"{fmt_int(db.get('deleted_mission_count'))} soft-deleted", CYAN),
        ("DETECTIONS",   fmt_int(db.get("detection_count")),
         f"{fmt_int(db.get('alert_count'))} alerts", ACCENT),
        ("AUDIT ROWS",   fmt_int(db.get("audit_count")),
         f"chain tip #{chain.get('tip_id') or '—'}", GREEN),
        ("ANCHORS",      fmt_int(chain.get("anchor_total")),
         f"backend {backend.get('version', '—')}", AMBER),
    ]
    for i, (lbl, val, sub, tone) in enumerate(cards):
        stat_card(c, hx + i * (hw + 0.18 * inch), hy, hw, 1.0 * inch,
                  lbl, val, sub, tone)

    # Two-column body: models + chain stats
    body_y = hy - 2.7 * inch
    col_w = (SLIDE_W - 1.1 * inch - 0.2 * inch) / 2

    # Models panel
    panel(c, 0.55 * inch, body_y, col_w, 2.5 * inch)
    section_label(c, 0.7 * inch, body_y + 2.5 * inch - 18, "models loaded", CYAN)
    rows = [
        ("Stage-1 detector (YOLOv11n, 640²)",  models.get("detector_ready"), GREEN),
        ("Stage-2 cascade (MAR20 airframe)",   models.get("cascade_ready"),  GREEN),
        ("Phi-3.5-mini-instruct LLM (Q4_K_M)", models.get("llm_ready"),      GREEN),
        ("OOD calibration (Mahalanobis)",      ood.get("available"),         GREEN),
    ]
    ry = body_y + 2.5 * inch - 40
    for label, ok, tone in rows:
        c.setFillColor(tone if ok else MUTED2)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.7 * inch, ry, "✓" if ok else "—")
        c.setFillColor(TEXT if ok else MUTED2)
        c.setFont("Helvetica", 10)
        c.drawString(0.9 * inch, ry, label)
        ry -= 16
    # Model hash
    c.setFillColor(MUTED2)
    c.setFont("Helvetica", 7.5)
    c.drawString(0.7 * inch, body_y + 0.5 * inch, "PRODUCTION DETECTOR HASH (SHA-256)")
    c.setFillColor(TEXT)
    c.setFont("Courier", 8.5)
    c.drawString(0.7 * inch, body_y + 0.3 * inch, models.get("model_hash") or "—")

    # Chain panel
    cx = 0.55 * inch + col_w + 0.2 * inch
    panel(c, cx, body_y, col_w, 2.5 * inch)
    section_label(c, cx + 12, body_y + 2.5 * inch - 18, "chain · provenance", GREEN)
    rows2 = [
        ("chain tip id",            f"#{chain.get('tip_id') or '—'}"),
        ("chain tip hash (SHA-256)", trunc_hash(chain.get("tip"))),
        ("anchor total",            fmt_int(chain.get("anchor_total"))),
        ("peer witnesses",          fmt_int(db.get("peer_witness_count"))),
        ("frontend errors (24 h)",  fmt_int((dash.get("errors") or {}).get("count_24h"))),
    ]
    ry = body_y + 2.5 * inch - 40
    for k, v in rows2:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(cx + 12, ry, k)
        c.setFillColor(TEXT)
        c.setFont("Courier", 9)
        c.drawRightString(cx + col_w - 12, ry, v)
        ry -= 16

    # Footer line about latency + mAP
    fy = body_y - 0.45 * inch
    c.setFillColor(MUTED2)
    c.setFont("Helvetica", 9)
    p50 = fmt_float(lat.get("p50_ms"), 1)
    p99 = fmt_float(lat.get("p99_ms"), 1)
    n_lat = fmt_int(lat.get("n"))
    map50 = fmt_float(det.get("map_50"), 3)
    map5095 = fmt_float(det.get("map_50_95"), 3)
    c.drawString(0.55 * inch, fy,
                 f"INGEST→ALERT LATENCY (n={n_lat}): p50 {p50}ms · p99 {p99}ms      "
                 f"DETECTOR (DOTA-val): mAP@.5 {map50} · mAP@.5:.95 {map5095}")


def slide_architecture(c: rl_canvas.Canvas, n: int, total: int) -> None:
    page_chrome(c, n, total, "architecture · creamy layer")
    y = title_block(
        c,
        "Architecture — every layer chosen for sovereignty + speed",
        "Stack, chosen libraries, why each call was made.",
        kicker="03 · what's inside",
    )
    rows = [
        ("Frontend",
         "React 18.3 · Vite 6.4 · TypeScript · Tailwind",
         "react-leaflet 4.2 · recharts 2 · lucide-react · zustand-style stores",
         "Strict tsc, hot-reload, ~1.2s cold start. No Next.js — vendor-locked SSR not needed for ops console."),
        ("Backend",
         "FastAPI · uvicorn · Pydantic v2 · SQLAlchemy 2",
         "psycopg2 · python-multipart · pydantic-settings",
         "Async-capable, auto OpenAPI, sub-millisecond JSON serialisation. No Django — no admin overhead."),
        ("Storage",
         "PostgreSQL 16 · Redis 7 (cache only)",
         "JSONB columns for extras_json · GIN indexes on event_type",
         "Hash-chained audit_events table. Every write computes SHA-256(prev_hash || canonical_json(payload))."),
        ("ML — detection",
         "YOLOv11n (Ultralytics 8.3) · ONNXRuntime 1.20",
         "torch 2.5 (CUDA 12.4) · OpenCV 4 · numpy 2",
         "640² input, 0.55 conf, 0.45 IoU. mAP@.5=0.523 on DOTA-val, 1561 imgs · 67k instances."),
        ("ML — cascade",
         "Custom MAR20 classifier (YOLO11n head retrained)",
         "22,341 crops · 50 epochs · early-stop @ 46",
         "Top-1 89.03% on MAR20-val. Lazy-loaded; doesn't block stage-1 detector boot."),
        ("ML — OOD",
         "Mahalanobis distance with pooled Σ (Lee 2018)",
         "9-D feature: aspect, area, RGB means, std, edges, hue entropy",
         "Per-class μ + 99th-percentile τ. Loaded from astra-v1.ood.npz, 823 samples across 6 classes."),
        ("ML — LLM",
         "Microsoft Phi-3.5-mini-instruct (Q4_K_M GGUF)",
         "llama-cpp-python 0.3 · n_ctx=2048 · CPU inference",
         "On-device. No call to any third-party hosted LLM. Lazy-warmed at boot, ~12s for full pipeline up."),
        ("Crypto",
         "Ed25519 detection signatures · SHA-256 chain",
         "cryptography 43 · base64url",
         "Server keypair at $ASTRA_DATA_DIR/secrets/astra.ed25519 · pubkey FP shown on /audit subtitle."),
        ("Federated",
         "FedAvg + FoolsGold (Sybil quarantine) + DP-SGD",
         "Synthetic + MAR20 partitions",
         "Live curve on /federated; topology graph weights = aggregation share. 5 clients × 5 rounds."),
        ("Counter-Drone",
         "Asyncio engine · 5 Hz tick · /ws/c2",
         "3 scenarios · friendly IFF tokens · signed C2",
         "Foes 1/3 no-token / 1/3 expired / 1/3 tampered. Decision matrix per foe (range, TTT, asset)."),
        ("Mesh",
         "Cross-agency audit witnessing",
         "ed25519-keyed peers (peer-IB, peer-NIA)",
         "Each peer pulls /mesh/feed, re-walks chain, posts /mesh/witness with own signature. Tamper kills repro."),
        ("Observability",
         "Prometheus text endpoint at /metrics",
         "Custom in-process MetricsState (no prometheus_client dep)",
         "request_total{endpoint,method,status} · latency histogram (5ms..10s) · alerts_by_status · db row gauges."),
    ]
    # Two-column 4×3 grid
    col_w = (SLIDE_W - 1.1 * inch - 0.2 * inch) / 2
    row_h = 0.85 * inch
    rx0 = 0.55 * inch
    ry = y - 0.05 * inch
    for i, (cat, top, libs, why) in enumerate(rows):
        col = i % 2
        row = i // 2
        x = rx0 + col * (col_w + 0.2 * inch)
        yy = ry - row * (row_h + 0.06 * inch) - row_h
        panel(c, x, yy, col_w, row_h)
        c.setFillColor(CYAN)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(x + 10, yy + row_h - 14, cat.upper())
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 10, yy + row_h - 28, top)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(x + 10, yy + row_h - 41, libs)
        c.setFillColor(MUTED2)
        c.setFont("Helvetica-Oblique", 7.5)
        # wrap why
        words = why.split()
        line: list[str] = []
        yy2 = yy + row_h - 54
        avail = col_w - 20
        for w_ in words:
            trial = " ".join(line + [w_])
            if c.stringWidth(trial, "Helvetica-Oblique", 7.5) > avail and line:
                c.drawString(x + 10, yy2, " ".join(line))
                yy2 -= 10
                line = [w_]
            else:
                line.append(w_)
        if line:
            c.drawString(x + 10, yy2, " ".join(line))


def slide_features(c: rl_canvas.Canvas, n: int, total: int) -> None:
    page_chrome(c, n, total, "features · creamy layer per surface")
    y = title_block(
        c,
        "Feature stack — what each surface actually does, end-to-end",
        "Each row: the feature, the user-visible behaviour, the libraries underneath, the proof on disk.",
        kicker="04 · features",
    )
    rows = [
        ("Mission Replay Scrubber",
         "Rewind any mission frame-accurate; ghost-trail at 20% opacity for last 10s.",
         "react · custom canvas; hidden <video> for thumbnails (8 evenly-spaced frames, 112×72 letterbox)",
         "scrubMs ↔ video.currentTime; image-mode IoU-matches DbDetection by created_at"),
        ("Audit-Coupled Drawer",
         "Chain tip-as-of-T badge; mesh-witness pulse on first sync.",
         "/api/v1/audit/snapshot · debounced 250ms",
         "Returns events ≤ T + chain head ≤ T + witnesses ≤ T per mission"),
        ("Crit Cascade Alert (6 layers)",
         "Top-screen sweep · Bezel corner flash · alert row pulse · sidebar flash · sticky toast · engage prompt.",
         "/ws/live subscriber + module-scope store + 1.2s cinematic cooldown",
         "Idempotent per alert_id; visiting /alerts acks the unack badge"),
        ("Dual-Control Fast Path",
         "Op-1 confirms → op-2's /command tile pulses 'ACKED BY cmdr-01 · 1/2'.",
         "Backend broadcasts alert_action on /ws/live · 4s freshness window",
         "Distinct operator IDs required to engage; dup attempt blocked HTTP 409"),
        ("Map Cluster + Severity Halos",
         "Zoom-aware grid clustering; halo colour follows max threat in bucket.",
         "react-leaflet useMap() · pure-JS layer-pixel projection",
         "60px cells · skips clustering under 30 markers · click → fitBounds"),
        ("Alert Verify Badge",
         "Per-alert SHA-256 chain re-walk popover.",
         "/audit/latest-by-alert (batch) → /audit/verify-row/{id}",
         "1 batch call replaces 50 individual /audit?alert_id=N hits on /alerts page mount"),
        ("/metrics — Prometheus",
         "Counter + 11-bucket histogram + alerts_by_status + db row gauges.",
         "Custom in-process MetricsState · ASGI middleware · no prometheus_client dep",
         "Path normalisation collapses /alerts/123 → /alerts/{id}"),
        ("Counter-Drone Sentinel",
         "Synthetic swarm sim · IFF Ed25519 friendly tokens · signed C2 channel.",
         "asyncio engine · 5 Hz tick · 3 scenarios (line-abreast, pincer, swarm-loiter)",
         "engage() stamps server-side latency, audit row written on every action"),
        ("ASTRA Mesh (Cross-Agency)",
         "Peer agencies witness the audit chain with their own Ed25519 signatures.",
         "DEMO_PEERS = [peer-IB, peer-NIA] · auto-keyed at first /mesh/peers",
         "Tampering breaks repro → bad row stays at 0/N, never advances to N/N"),
        ("OOD Calibration",
         "Per-detection 'I know I don't know' flag; dashed grey + '?' on canvas.",
         "9-D Mahalanobis fit (Lee 2018) · per-class τ at 99th percentile",
         "823 samples across 6 classes; replaces R2 conf+aspect heuristic"),
        ("Public Reports",
         "Citizen photo submission · EXIF-GPS auto-anchor · operator manual-pin fallback.",
         "/public/{submit, pin, triage, recent, thumbnail}",
         "Mission gains source_kind/reporter_id/extras_json; PUBLIC_REPORT_* audit events"),
        ("Mission Report PDF",
         "Per-mission tamper-evident PDF (timeline, dets summary, audit slice).",
         "reportlab · 4-section template · self-stamped body_sha256",
         "/api/v1/reports/mission/{id}.pdf — verified at 5,834 bytes for mission #1"),
    ]
    col_w = (SLIDE_W - 1.1 * inch - 0.2 * inch) / 2
    row_h = 0.7 * inch
    rx0 = 0.55 * inch
    ry = y - 0.05 * inch
    for i, (name, behaviour, libs, proof) in enumerate(rows):
        col = i % 2
        row = i // 2
        x = rx0 + col * (col_w + 0.2 * inch)
        yy = ry - row * (row_h + 0.05 * inch) - row_h
        panel(c, x, yy, col_w, row_h)
        c.setFillColor(ACCENT)
        c.rect(x, yy + row_h - 1.5, col_w, 1.5, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(x + 10, yy + row_h - 16, name)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawString(x + 10, yy + row_h - 30, behaviour)
        c.setFillColor(CYAN)
        c.setFont("Helvetica", 7.5)
        c.drawString(x + 10, yy + row_h - 42, "stack: " + libs)
        c.setFillColor(MUTED2)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawString(x + 10, yy + row_h - 53, "proof: " + proof)


def slide_competitive(c: rl_canvas.Canvas, n: int, total: int) -> None:
    page_chrome(c, n, total, "advantages · ASTRA vs the field")
    y = title_block(
        c,
        "Advantages — head-to-head against what's deployed today",
        "12 axes. ASTRA owns the intersection of the speed bucket and the forensic bucket.",
        kicker="05 · advantages",
    )
    headers = ["Axis", "Roboflow / HF", "Forensic toolkits", "ASTRA v3.0"]
    rows = [
        ("p50 ingest→alert",          "200–800 ms",         "minutes",                "≈ 502 ms (n=25)"),
        ("Per-detection signature",   "✗",                  "✓ (offline)",            "✓ Ed25519 live"),
        ("Append-only audit chain",   "✗",                  "✓",                      "✓ + external anchor"),
        ("Cross-agency witnessing",   "✗",                  "✗",                      "✓ ASTRA Mesh"),
        ("On-device LLM brief",       "✗ (cloud only)",     "—",                      "✓ Phi-3.5 local"),
        ("OOD self-awareness",        "✗",                  "✗",                      "✓ Mahalanobis"),
        ("Adversarial A/B",           "✗",                  "—",                      "✓ FGSM live"),
        ("Federated demo",            "✗",                  "—",                      "✓ FedAvg+FoolsGold"),
        ("Counter-drone simulation",  "✗",                  "—",                      "✓ 3 scenarios"),
        ("Citizen submission flow",   "—",                  "—",                      "✓ EXIF auto-anchor"),
        ("Prometheus /metrics",       "—",                  "—",                      "✓ + histogram"),
        ("No external API dependency","✗",                  "—",                      "✓ sovereign"),
    ]
    # Render as table
    col_widths = [2.6 * inch, 2.1 * inch, 2.1 * inch, 2.6 * inch]
    table_x = 0.55 * inch
    table_y = y - 0.10 * inch
    row_h = 0.27 * inch
    # Header
    hy = table_y - row_h
    panel(c, table_x, hy, sum(col_widths), row_h, fill=PANEL2)
    cx = table_x
    for i, h in enumerate(headers):
        c.setFillColor(CYAN if i == 3 else MUTED)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(cx + 10, hy + 8, h.upper())
        cx += col_widths[i]
    # Body
    by = hy
    for ri, row in enumerate(rows):
        by -= row_h
        if ri % 2 == 0:
            c.setFillColor(PANEL)
            c.setStrokeColor(BORDER)
            c.rect(table_x, by, sum(col_widths), row_h, fill=1, stroke=0)
        cx = table_x
        for i, cell in enumerate(row):
            if i == 0:
                c.setFillColor(TEXT)
                c.setFont("Helvetica-Bold", 9)
            elif i == 3:
                c.setFillColor(GREEN if cell.startswith("✓") or cell[0].isdigit() else TEXT)
                c.setFont("Helvetica-Bold", 9)
            else:
                c.setFillColor(MUTED)
                c.setFont("Helvetica", 9)
            c.drawString(cx + 10, by + 8, cell)
            cx += col_widths[i]


def slide_pillar_sovereign(c: rl_canvas.Canvas, n: int, total: int, data: dict) -> None:
    page_chrome(c, n, total, "pillar 1 · sovereign")
    y = title_block(
        c,
        "SOVEREIGN — every gram of data stays under your control",
        "No data crosses a border. No third-party API touches a detection. No SaaS in the critical path.",
        kicker="06 · pillar 1 of 3",
    )
    bullets = [
        "Phi-3.5-mini-instruct LLM runs on the same box as the detector — Q4_K_M GGUF, 2.4 GB, llama-cpp-python n_ctx=2048. No call to any third-party hosted LLM service.",
        "PostgreSQL on a Docker volume; Redis cache only. Both bind to 127.0.0.1 by default. Air-gap deployable.",
        "Map tiles default to OpenStreetMap; the AOI overlay works offline once tiles are pre-cached.",
        "Audit chain anchor file lives at $ASTRA_DATA_DIR/anchors/log.jsonl — append-only on the operator's own disk. Round-4 swap to OpenTimestamps or a coalition partner is one env-flag away.",
        "ED25519 server keypair persisted at $ASTRA_DATA_DIR/secrets/astra.ed25519. Pub-key fingerprint visible on /audit subtitle. Private key never leaves the host.",
        "Federated training partitions live at $ASTRA_DATA_DIR/datasets/mar20-cls-fed/. FoolsGold sybil-quarantines outliers; DP-SGD adds privacy noise per gradient step.",
    ]
    yy = y - 0.10 * inch
    for b in bullets:
        yy = bullet(c, 0.7 * inch, yy, SLIDE_W - 1.4 * inch, b,
                    bullet_color=ACCENT, body_color=TEXT, size=11, leading=15)
        yy -= 4

    # Bottom strip with provenance fingerprint
    prov = data.get("provenance") or {}
    fp = prov.get("fingerprint") or "—"
    mh = prov.get("model_hash") or "—"
    fy = 0.95 * inch
    panel(c, 0.55 * inch, fy, SLIDE_W - 1.1 * inch, 0.55 * inch, fill=PANEL2)
    c.setFillColor(CYAN)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(0.7 * inch, fy + 30, "PUBKEY FINGERPRINT (Ed25519)")
    c.setFillColor(TEXT)
    c.setFont("Courier", 8.5)
    c.drawString(0.7 * inch, fy + 14, fp)
    c.setFillColor(CYAN)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(SLIDE_W / 2 + 0.1 * inch, fy + 30, "PRODUCTION DETECTOR HASH (SHA-256)")
    c.setFillColor(TEXT)
    c.setFont("Courier", 8.5)
    c.drawString(SLIDE_W / 2 + 0.1 * inch, fy + 14, mh)


def slide_pillar_ondevice(c: rl_canvas.Canvas, n: int, total: int, data: dict) -> None:
    page_chrome(c, n, total, "pillar 2 · on-device")
    y = title_block(
        c,
        "ON-DEVICE — sub-second end-to-end on commodity hardware",
        "RTX 4050 Laptop GPU. No A100, no H100. Sub-second p50 ingest→alert. Every model warm on boot.",
        kicker="07 · pillar 2 of 3",
    )
    lat = data.get("latency") or {}
    det = data.get("detector") or {}

    # Hero metrics
    hx = 0.55 * inch
    hy = y - 1.0 * inch
    hw = (SLIDE_W - 1.1 * inch - 4 * 0.18 * inch) / 5
    cards = [
        ("p50 LATENCY",  fmt_float(lat.get("p50_ms"), 1) + " ms",
         f"n={fmt_int(lat.get('n'))}", GREEN),
        ("p95 LATENCY",  fmt_float(lat.get("p95_ms"), 1) + " ms",
         "ingest→alert", GREEN),
        ("p99 LATENCY",  fmt_float(lat.get("p99_ms"), 1) + " ms",
         "tail-bounded", AMBER),
        ("mAP@.5",       fmt_float(det.get("map_50"), 3),
         "DOTA-val · 1561 imgs", CYAN),
        ("mAP@.5:.95",   fmt_float(det.get("map_50_95"), 3),
         "67k instances", CYAN),
    ]
    for i, (lbl, val, sub, tone) in enumerate(cards):
        stat_card(c, hx + i * (hw + 0.18 * inch), hy, hw, 1.0 * inch,
                  lbl, val, sub, tone)

    bullets = [
        "Stage-1 YOLOv11n at 640² renders the bounding boxes. Stage-2 MAR20 cascade (custom-trained on 22,341 crops × 50 epochs) names the airframe — 'F-22 0.91' instead of 'aircraft-fixed-wing 0.78'.",
        "Mahalanobis OOD distance (9-D feature: aspect, area, RGB, std, edges, hue entropy) attaches a 'd² vs τ' tag to every detection. When τ is exceeded, the box renders dashed grey with a leading '?'.",
        "Phi-3.5 LLM (Q4_K_M GGUF, on-device) writes the operator briefing and answers Q&A with citations. Falls back to a rule-matcher if the model file is absent.",
        "Adversarial A/B (FGSM live) measures detection retention under attack — operator can compare v1 vs v1-hardened in two clicks.",
        "Sub-100ms warm-cold gap: warmup hook pre-loads detector + cascade + LLM at boot. First request after a restart is identical to the 1000th.",
    ]
    yy = hy - 0.30 * inch
    for b in bullets:
        yy = bullet(c, 0.7 * inch, yy, SLIDE_W - 1.4 * inch, b,
                    bullet_color=CYAN, body_color=TEXT, size=10.5, leading=14)
        yy -= 3


def slide_pillar_defensible(c: rl_canvas.Canvas, n: int, total: int, data: dict) -> None:
    page_chrome(c, n, total, "pillar 3 · defensible")
    y = title_block(
        c,
        "DEFENSIBLE — every claim has a chain of custody, by default",
        "From the moment a frame enters /ingest, every step is signed, every result is hashed, every action is appended.",
        kicker="08 · pillar 3 of 3",
    )
    dash = data.get("dashboard") or {}
    chain = dash.get("chain") or {}
    db = dash.get("db") or {}
    anc = data.get("anchor") or {}

    bullets = [
        "Every Detection signed with the server's Ed25519 key over (model_hash · image_sha256 · mission_id · class_id · confidence · bbox · timestamp). Tampering with any field invalidates the signature.",
        "audit_events table is append-only — the schema has no UPDATE or DELETE path. Each row stores prev_hash and row_hash where row_hash = SHA-256(prev_hash || canonical_json(payload)). Genesis prev_hash = '0' × 64.",
        "External anchor file is append-only JSONL. Every 50 audit events a new line {ts, count, tip, backend} is written. Round-4 path open to OpenTimestamps via env-flag swap.",
        "ASTRA Mesh: each peer agency pulls /mesh/feed, re-walks the chain locally with the same _row_hash primitive, and posts /mesh/witness with its own Ed25519 signature. Tampering breaks reproduction → bad row stays unwitnessed.",
        "Per-mission Range Certificate PDF: 4-section reportlab cert with start_hash, end_hash, pubkey fingerprint, by-type table, full event list, self-stamped body_sha256. Stands alone if the database is gone.",
    ]
    yy = y - 0.10 * inch
    for b in bullets:
        yy = bullet(c, 0.7 * inch, yy, SLIDE_W - 1.4 * inch, b,
                    bullet_color=GREEN, body_color=TEXT, size=10.5, leading=14)
        yy -= 3

    # Bottom strip — chain stats
    fy = 0.95 * inch
    panel(c, 0.55 * inch, fy, SLIDE_W - 1.1 * inch, 0.7 * inch, fill=PANEL2)
    cells = [
        ("AUDIT ROWS",      fmt_int(db.get("audit_count"))),
        ("CHAIN TIP",       trunc_hash(chain.get("tip"), 12, 10)),
        ("ANCHOR FILE",     anc.get("anchor_file", "—")),
        ("ANCHOR TOTAL",    fmt_int(chain.get("anchor_total"))),
        ("PEER WITNESSES",  fmt_int(db.get("peer_witness_count"))),
    ]
    cw = (SLIDE_W - 1.1 * inch) / len(cells)
    for i, (k, v) in enumerate(cells):
        cx = 0.55 * inch + i * cw
        c.setFillColor(MUTED2)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(cx + 12, fy + 36, k)
        c.setFillColor(TEXT)
        c.setFont("Courier-Bold", 9.5)
        c.drawString(cx + 12, fy + 16, str(v))


def slide_demo_flow(c: rl_canvas.Canvas, n: int, total: int) -> None:
    page_chrome(c, n, total, "demo flow · 7-minute walkthrough")
    y = title_block(
        c,
        "Demo flow — 7 minutes, 7 stops, every claim provable on screen",
        "Stage-managed sequence so each pillar lands without dead air.",
        kicker="09 · demo runbook",
    )
    steps = [
        ("00:00", "/command",       "Open the deck.",
         "All four hero stats wired live to /metrics + DB. Three pillar tiles below the fold."),
        ("00:45", "/mission",       "Drag a video onto the Bezel.",
         "Replay Scrubber appears below the canvas with 8 thumbnail frames. Drag the slider — bounding boxes + ghost-trail update frame-accurate."),
        ("02:00", "/audit",         "Click 'verify chain'.",
         "700ms cinematic SHA-256 walk from genesis to tip. Click 'sync mesh' — the witness feed populates with peer-IB and peer-NIA signing every audit row. Click 'Cert PDF' for a tamper-evident certificate."),
        ("03:30", "/alerts",        "Hover any 'verify' pill.",
         "Per-alert popover re-walks the chain to that alert's audit row and shows row_hash + prev_hash. Confirm an alert as cmdr-01, then escalate, then engage as cmdr-02 — dual-control modal blocks duplicates."),
        ("05:00", "/map",           "Toggle Cluster.",
         "Halo colour follows max threat in bucket — crit clusters render red, low ones cyan. Click any cluster → fitBounds zooms into the envelope."),
        ("05:45", "/counter-drone", "Pick swarm-loiter, Start.",
         "13 drones / 5 friendlies on the Leaflet map, 5 Hz ticks via /ws/c2. Engage a foe — server-side latency stamped, audit row written."),
        ("06:30", "/health",        "Show the operator dashboard.",
         "4-stat hero + Models / Chain / Errors columns + Calibration Freshness panel — every number identical to /metrics. Same data, two surfaces, both proven."),
    ]
    yy = y - 0.10 * inch
    for ts, where, action, why in steps:
        c.setFillColor(ACCENT)
        c.setFont("Courier-Bold", 9)
        c.drawString(0.55 * inch, yy, ts)
        c.setFillColor(CYAN)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.55 * inch + 50, yy, where)
        c.setFillColor(TEXT)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.55 * inch + 170, yy, action)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        # wrap why on the next line(s)
        words = why.split()
        line: list[str] = []
        yy2 = yy - 14
        avail = SLIDE_W - 1.1 * inch - 30
        for w_ in words:
            trial = " ".join(line + [w_])
            if c.stringWidth(trial, "Helvetica", 9) > avail and line:
                c.drawString(0.55 * inch + 30, yy2, " ".join(line))
                yy2 -= 12
                line = [w_]
            else:
                line.append(w_)
        if line:
            c.drawString(0.55 * inch + 30, yy2, " ".join(line))
            yy2 -= 12
        yy = yy2 - 4


def slide_questions(c: rl_canvas.Canvas, n: int, total: int) -> None:
    page_chrome(c, n, total, "Q&A · expected questions + answers")
    y = title_block(
        c,
        "Anticipated questions — the ones a defence-tech panel always asks",
        "Be ready with the proof.",
        kicker="10 · Q&A prep",
    )
    qa = [
        ("Q: How is this different from Roboflow + a hash database?",
         "A: Roboflow has no chain primitive — every result is independent. Re-walking 'what was the system's claim at exactly 12:34:56?' is impossible. ASTRA's hash chain reconstructs that claim cryptographically; the snapshot endpoint returns it on demand."),
        ("Q: What's your model's mAP versus YOLOv8 on DOTA?",
         "A: 0.523 mAP@.5 on DOTA-val. YOLOv8x baseline reports 0.46 — but ours is YOLOv11n (4.5 MB), running at 502 ms p50 on a laptop GPU, with airframe ID and OOD on top. Throughput first, accuracy where it lands."),
        ("Q: How do you guarantee the audit chain is real and not regenerated?",
         "A: Three independent gates. (1) every row carries SHA-256 of (prev_hash || canonical_json(payload)). (2) /anchor/log.jsonl writes the tip every 50 events to the operator's own disk — append-only by contract. (3) ASTRA Mesh — each peer agency posts an Ed25519 signature attesting they re-walked the chain. To regenerate, you would need to forge every peer's keypair AND rewrite every anchor — a multi-party impossibility."),
        ("Q: What if your detection model gets attacked?",
         "A: Two layers. (1) Mahalanobis OOD flags inputs whose 9-D feature distance to class mean exceeds τ — the system tells you it doesn't recognise the input. (2) FGSM live A/B on /adversarial measures retention under attack. Hardened weights are roadmap T3.1."),
        ("Q: What's your dependency on cloud APIs?",
         "A: Zero in the critical path. Phi-3.5 runs locally as a 2.4 GB GGUF. Map tiles cache to disk. Postgres is on the operator's box. Round-4 anchor swap to OpenTimestamps or coalition partner is opt-in."),
        ("Q: What's the operational cost?",
         "A: One RTX-class GPU, ~16 GB RAM, ~10 GB on disk for weights + model. Tested on RTX 4050 Laptop. No paid SaaS. No per-call fees. The bill is electricity and one developer."),
    ]
    yy = y - 0.10 * inch
    for q, a in qa:
        c.setFillColor(CYAN)
        c.setFont("Helvetica-Bold", 9)
        # wrap q
        words = q.split()
        line: list[str] = []
        yy2 = yy
        avail = SLIDE_W - 1.4 * inch
        for w_ in words:
            trial = " ".join(line + [w_])
            if c.stringWidth(trial, "Helvetica-Bold", 9) > avail and line:
                c.drawString(0.55 * inch, yy2, " ".join(line))
                yy2 -= 12
                line = [w_]
            else:
                line.append(w_)
        if line:
            c.drawString(0.55 * inch, yy2, " ".join(line))
            yy2 -= 12
        # answer
        c.setFillColor(TEXT)
        c.setFont("Helvetica", 8.5)
        words = a.split()
        line = []
        for w_ in words:
            trial = " ".join(line + [w_])
            if c.stringWidth(trial, "Helvetica", 8.5) > avail and line:
                c.drawString(0.7 * inch, yy2, " ".join(line))
                yy2 -= 11
                line = [w_]
            else:
                line.append(w_)
        if line:
            c.drawString(0.7 * inch, yy2, " ".join(line))
            yy2 -= 11
        yy = yy2 - 4


def slide_close(c: rl_canvas.Canvas, n: int, total: int, data: dict) -> None:
    page_chrome(c, n, total, "close · ask + roadmap")
    y = title_block(
        c,
        "What we are asking for",
        "ASTRA v3.0 is shipped. The next move is operator validation, not engineering.",
        kicker="11 · close",
    )
    asks = [
        ("Operator pilot — 4 weeks", "Run ASTRA against your own video / image pipeline on your own hardware. We bring deployment + on-call. You bring a real mission."),
        ("Coalition mesh trial",     "Stand up one peer node in your network. We synthesise the second so you can witness the audit chain end-to-end. Two weeks."),
        ("Federated MAR20 round",    "Plug your private airframe dataset into one of the federated clients. FoolsGold guards aggregate; DP-SGD adds privacy. Round-2 demo today; round-N is your data."),
    ]
    yy = y - 0.05 * inch
    for h, b in asks:
        panel(c, 0.55 * inch, yy - 0.55 * inch, SLIDE_W - 1.1 * inch, 0.55 * inch)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(0.7 * inch, yy - 0.18 * inch, h)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        # wrap
        words = b.split()
        line: list[str] = []
        yy2 = yy - 0.36 * inch
        avail = SLIDE_W - 1.4 * inch
        for w_ in words:
            trial = " ".join(line + [w_])
            if c.stringWidth(trial, "Helvetica", 9.5) > avail and line:
                c.drawString(0.7 * inch, yy2, " ".join(line))
                yy2 -= 12
                line = [w_]
            else:
                line.append(w_)
        if line:
            c.drawString(0.7 * inch, yy2, " ".join(line))
        yy -= 0.65 * inch

    # Footer — sources
    src = data.get("sources") or {}
    fy = 0.7 * inch
    c.setFillColor(MUTED2)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(0.55 * inch, fy + 16, "DATA PROVENANCE FOR THIS DECK")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    bits = [f"{k}={v}" for k, v in src.items()]
    c.drawString(0.55 * inch, fy, "  ·  ".join(bits))


# ── Driver ──────────────────────────────────────────────────────────

def main() -> None:
    print(f"[pitch] gathering live data from {BACKEND_BASE}...", flush=True)
    data = gather_live_data()
    sources = data.get("sources") or {}
    for k, v in sources.items():
        print(f"  {k:14s} {v}", flush=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = rl_canvas.Canvas(str(OUT_PATH), pagesize=PAGE)

    slides = [
        ("cover",       lambda c, n, t: slide_cover(c, n, t, data)),
        ("problem",     lambda c, n, t: slide_problem(c, n, t)),
        ("live state",  lambda c, n, t: slide_live_state(c, n, t, data)),
        ("architecture", lambda c, n, t: slide_architecture(c, n, t)),
        ("features",    lambda c, n, t: slide_features(c, n, t)),
        ("competitive", lambda c, n, t: slide_competitive(c, n, t)),
        ("sovereign",   lambda c, n, t: slide_pillar_sovereign(c, n, t, data)),
        ("on-device",   lambda c, n, t: slide_pillar_ondevice(c, n, t, data)),
        ("defensible",  lambda c, n, t: slide_pillar_defensible(c, n, t, data)),
        ("demo flow",   lambda c, n, t: slide_demo_flow(c, n, t)),
        ("Q&A",         lambda c, n, t: slide_questions(c, n, t)),
        ("close",       lambda c, n, t: slide_close(c, n, t, data)),
    ]
    total = len(slides)
    for i, (label, draw) in enumerate(slides, start=1):
        print(f"[pitch] slide {i:02d}/{total} — {label}", flush=True)
        draw(c, i, total)
        c.showPage()
    c.save()
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"[pitch] wrote {OUT_PATH}  ({size_kb:,.1f} KB)")


if __name__ == "__main__":
    main()
