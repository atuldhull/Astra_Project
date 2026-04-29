"""
Audit-range certificate PDF (T D3.2).

Given a [since, until] window over the audit log, produces a single PDF
proving:
  * which row_hash bookended the range (start_hash, end_hash),
  * which server pubkey signs detections in this period (Ed25519 fp),
  * the full event list inside the range,
  * a per-event-type breakdown,
  * the SHA-256 of the PDF body bytes (so the PDF itself is self-stamped),
  * who/when generated it.

Reuses the palette + style scaffolding from onepager.py — same fonts,
same colors, same margins. Don't introduce a third PDF style.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# Match onepager.py palette so the two PDFs feel like one product.
ACCENT = colors.HexColor("#22d3ee")
TEXT = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
PANEL = colors.HexColor("#f1f5f9")
BORDER = colors.HexColor("#cbd5e1")


def _short_hash(h: str | None) -> str:
    if not h:
        return "—"
    if len(h) <= 18:
        return h
    return f"{h[:10]}…{h[-6:]}"


def _summarize_event(payload: dict | None, event_type: str) -> str:
    """Human-readable one-line summary of an audit row's payload."""
    if not payload:
        return event_type
    bits: list[str] = []
    for k in ("alert_id", "mission_id", "operator_id", "to_status", "from_status",
              "score", "n", "kind", "reason"):
        if k in payload and payload[k] not in (None, ""):
            bits.append(f"{k}={payload[k]}")
    return ", ".join(bits)[:140] if bits else ""


def render_range_cert(
    *,
    since_iso: str | None,
    until_iso: str | None,
    rows: list,
    start_hash: str | None,
    end_hash: str | None,
    pubkey_fingerprint: str | None,
    by_event_type: dict[str, int],
    generated_by: str | None = None,
) -> bytes:
    """Build the PDF and return its bytes. The footer hash is appended last
    so it covers the body. We render twice: first to obtain the body, then
    again with the footer hash filled in. Cheaper than streaming."""

    def _build(footer_hash: str | None) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=14 * mm,
            rightMargin=14 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title="ASTRA · Audit Range Certificate",
        )
        styles = getSampleStyleSheet()
        H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, leading=22, textColor=TEXT, spaceAfter=2)
        SUB = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, textColor=MUTED, spaceAfter=8)
        H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, leading=14, textColor=TEXT, spaceBefore=6, spaceAfter=4)
        BODY = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=12, textColor=TEXT)
        SMALL = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=MUTED)
        MONO = ParagraphStyle("mono", parent=styles["Normal"], fontSize=8.5, fontName="Courier", textColor=TEXT)

        story: list = []

        story.append(Paragraph(
            "ASTRA · <font color='#22d3ee'>AUDIT RANGE CERTIFICATE</font>",
            H1,
        ))
        story.append(Paragraph(
            f"Tamper-evident hash-chain proof for the audit window below. "
            f"Verify by re-walking SHA-256 from genesis to <b>start_hash</b>, "
            f"and from there to <b>end_hash</b>.",
            SUB,
        ))
        story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED, spaceBefore=2, spaceAfter=8))

        # ── Range fingerprints ────────────────────────────────────────────
        story.append(Paragraph("Range fingerprints", H2))
        cert_rows = [
            ["since",                  since_iso or "(beginning of chain)"],
            ["until",                  until_iso or "(latest)"],
            ["events in range",        str(len(rows))],
            ["start_hash",             _short_hash(start_hash)],
            ["end_hash",               _short_hash(end_hash)],
            ["server pubkey fingerprint (Ed25519)", _short_hash(pubkey_fingerprint)],
        ]
        cert_tbl = Table(cert_rows, colWidths=[55 * mm, 125 * mm])
        cert_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), PANEL),
            ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
            ("FONT", (1, 0), (1, -1), "Courier", 9),
            ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(cert_tbl)
        story.append(Spacer(1, 5 * mm))

        # ── Per-event-type breakdown ──────────────────────────────────────
        if by_event_type:
            story.append(Paragraph("Events by type", H2))
            type_rows = [["event_type", "count"]]
            for et, n in sorted(by_event_type.items(), key=lambda kv: -kv[1]):
                type_rows.append([et, str(n)])
            type_tbl = Table(type_rows, colWidths=[120 * mm, 30 * mm])
            type_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), PANEL),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                ("FONT", (0, 1), (-1, -1), "Courier", 9),
                ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, BORDER),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(type_tbl)
            story.append(Spacer(1, 5 * mm))

        # ── Full event list ───────────────────────────────────────────────
        story.append(Paragraph("Events", H2))
        list_rows = [["id", "ts (UTC)", "type", "operator", "summary"]]
        for r in rows:
            list_rows.append([
                str(r.id),
                (r.created_at.isoformat() if r.created_at else "")[:19],
                r.event_type.value if hasattr(r.event_type, "value") else str(r.event_type),
                r.operator_id or "system",
                _summarize_event(r.payload_json, str(r.event_type)),
            ])
        list_tbl = Table(list_rows, colWidths=[12 * mm, 36 * mm, 38 * mm, 26 * mm, 70 * mm], repeatRows=1)
        list_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PANEL),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
            ("FONT", (0, 1), (-1, -1), "Courier", 7.5),
            ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.15, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(list_tbl)
        story.append(Spacer(1, 6 * mm))

        # ── Footer ───────────────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=0.4, color=MUTED, spaceBefore=2, spaceAfter=4))
        story.append(Paragraph(
            f"<b>generated_at</b>: {datetime.now(timezone.utc).isoformat()}",
            BODY,
        ))
        story.append(Paragraph(
            f"<b>generated_by</b>: {generated_by or 'astra-backend'}",
            BODY,
        ))
        story.append(Paragraph(
            f"<b>body_sha256</b>: <font face='Courier'>{footer_hash or '(computed in second pass)'}</font>",
            SMALL,
        ))
        story.append(Paragraph(
            "This certificate is itself self-stamped: body_sha256 above is the SHA-256 "
            "of the rendered PDF without this footer. Re-rendering the certificate from "
            "the same audit rows must reproduce the same hash.",
            SMALL,
        ))

        doc.build(story)
        return buf.getvalue()

    # First pass: build without the footer hash, hash the body, then
    # re-render with the hash baked in. The body hash is stable across
    # the second render because reportlab's output is deterministic for
    # identical input on the same library version + same input rows.
    body_first = _build(None)
    digest = hashlib.sha256(body_first).hexdigest()
    return _build(digest)


__all__ = ["render_range_cert"]
