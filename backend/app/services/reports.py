"""
Mission report PDF generator.

Produces a single-mission summary with:
  - Mission metadata + AOI corners
  - Summary statistics (detection + alert counts, class distribution)
  - Top-N threat alerts with narratives
  - Relevant audit events for the mission
  - SHA-256 integrity hash of the report body at the footer

Built with reportlab — pure Python, no external system dependencies.
Returns PDF bytes; caller decides whether to stream, save, or attach.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.db.models import Alert, AuditEvent, Detection, Mission

# ASTRA color palette (muted for print)
NAVY = colors.HexColor("#0a0f14")
PANEL = colors.HexColor("#1a222d")
BORDER = colors.HexColor("#23303d")
TEXT = colors.HexColor("#14181e")  # dark (for print legibility)
MUTED = colors.HexColor("#4a5566")
ACCENT = colors.HexColor("#c55a0e")  # muted orange for print
THREAT_CRIT = colors.HexColor("#b02a37")
THREAT_HIGH = colors.HexColor("#d2691e")
THREAT_LOW = colors.HexColor("#2d7f4f")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"],
            fontSize=22, leading=26, textColor=NAVY, spaceAfter=6, spaceBefore=0,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"],
            fontSize=14, leading=18, textColor=NAVY, spaceAfter=4, spaceBefore=14,
        ),
        "h3": ParagraphStyle(
            "H3", parent=base["Heading3"],
            fontSize=11, leading=14, textColor=ACCENT, spaceAfter=3, spaceBefore=10,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"],
            fontSize=9.5, leading=13, textColor=TEXT, spaceAfter=3,
        ),
        "muted": ParagraphStyle(
            "Muted", parent=base["BodyText"],
            fontSize=8.5, leading=11, textColor=MUTED,
        ),
        "mono": ParagraphStyle(
            "Mono", parent=base["BodyText"],
            fontSize=8.5, leading=11, fontName="Courier", textColor=MUTED,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Heading1"],
            fontSize=36, leading=40, textColor=NAVY, spaceAfter=8, alignment=0,
        ),
        "cover_tag": ParagraphStyle(
            "CoverTag", parent=base["BodyText"],
            fontSize=10, leading=14, textColor=ACCENT, spaceAfter=6,
            fontName="Courier",
        ),
    }


def _fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _threat_color(score: float) -> colors.Color:
    if score >= 0.75: return THREAT_CRIT
    if score >= 0.55: return THREAT_HIGH
    return THREAT_LOW


def generate_mission_report(db: Session, mission_id: int) -> bytes:
    """Render a PDF for the given mission. Returns PDF bytes."""
    mission = db.get(Mission, mission_id)
    if not mission:
        raise ValueError(f"mission {mission_id} not found")

    detections = db.query(Detection).filter(Detection.mission_id == mission_id).all()
    alerts = (
        db.query(Alert)
        .filter(Alert.mission_id == mission_id)
        .order_by(Alert.threat_score.desc())
        .all()
    )
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.mission_id == mission_id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )

    # AOI parse
    aoi = None
    if mission.aoi_corners_json:
        try:
            aoi = json.loads(mission.aoi_corners_json)
        except Exception:
            pass

    # Class distribution
    cls_counts: dict[str, int] = {}
    for d in detections:
        cls_counts[d.class_name] = cls_counts.get(d.class_name, 0) + 1

    # Status breakdown
    status_counts = {"pending": 0, "confirmed": 0, "rejected": 0, "escalated": 0}
    for a in alerts:
        key = a.status.value if hasattr(a.status, "value") else str(a.status)
        status_counts[key] = status_counts.get(key, 0) + 1

    # ── Build PDF ────────────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title=f"ASTRA Mission Report · {mission.name}",
        author="ASTRA",
    )
    s = _styles()
    story = []

    # Cover header
    story.append(Paragraph("ASTRA · MISSION REPORT", s["cover_tag"]))
    story.append(Paragraph(mission.name, s["cover_title"]))
    story.append(HRFlowable(width="100%", thickness=0.75, color=ACCENT, spaceAfter=10))

    meta_rows = [
        ["Mission ID",        f"#{mission.id}"],
        ["Created (UTC)",     _fmt_ts(mission.created_at)],
        ["Generated (UTC)",   _fmt_ts(datetime.now(timezone.utc))],
        ["Source",            mission.source_path.split("\\")[-1].split("/")[-1]],
        ["Detections",        str(len(detections))],
        ["Alerts",            f"{len(alerts)} total ({status_counts['confirmed']} confirmed, {status_counts['rejected']} rejected, {status_counts['escalated']} escalated, {status_counts['pending']} pending)"],
        ["AOI georeferenced", "yes" if aoi else "no"],
    ]
    meta_tbl = Table(meta_rows, colWidths=[45 * mm, 125 * mm])
    meta_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, BORDER),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 8))

    # AOI box
    if aoi:
        story.append(Paragraph("Area of Interest (corner coordinates)", s["h3"]))
        aoi_rows = [
            ["Top-Left",     f"{aoi['top_left'][0]:.6f}, {aoi['top_left'][1]:.6f}"],
            ["Top-Right",    f"{aoi['top_right'][0]:.6f}, {aoi['top_right'][1]:.6f}"],
            ["Bottom-Right", f"{aoi['bottom_right'][0]:.6f}, {aoi['bottom_right'][1]:.6f}"],
            ["Bottom-Left",  f"{aoi['bottom_left'][0]:.6f}, {aoi['bottom_left'][1]:.6f}"],
        ]
        aoi_tbl = Table(aoi_rows, colWidths=[35 * mm, 135 * mm])
        aoi_tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Courier"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("TEXTCOLOR", (1, 0), (-1, -1), TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(aoi_tbl)

    # Class distribution
    if cls_counts:
        story.append(Paragraph("Detection Summary", s["h2"]))
        cls_rows = [["Class", "Count"]]
        for cls, cnt in sorted(cls_counts.items(), key=lambda x: -x[1]):
            cls_rows.append([cls, str(cnt)])
        cls_tbl = Table(cls_rows, colWidths=[80 * mm, 25 * mm])
        cls_tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), PANEL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 1), (0, -1), "Courier"),
            ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.25, BORDER),
        ]))
        story.append(cls_tbl)

    # ── R3: Stage-2 cascade airframes ────────────────────────────────────
    airframe_counts: dict[str, int] = {}
    airframe_confs: dict[str, list[float]] = {}
    for d in detections:
        ex = json.loads(d.extras_json) if d.extras_json else {}
        if ex.get("airframe"):
            af = ex["airframe"]
            airframe_counts[af] = airframe_counts.get(af, 0) + 1
            airframe_confs.setdefault(af, []).append(float(ex.get("airframe_confidence", 0.0)))
    if airframe_counts:
        story.append(Paragraph("Stage-2 Cascade · Fine-Grained Airframe ID (MAR20)", s["h2"]))
        af_rows = [["Airframe", "Count", "Mean conf", "Max conf"]]
        for af, cnt in sorted(airframe_counts.items(), key=lambda x: -x[1]):
            confs = airframe_confs[af]
            mean = sum(confs) / len(confs)
            mx = max(confs)
            af_rows.append([af, str(cnt), f"{mean:.3f}", f"{mx:.3f}"])
        af_tbl = Table(af_rows, colWidths=[60 * mm, 25 * mm, 30 * mm, 30 * mm])
        af_tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), PANEL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 1), (-1, -1), "Courier"),
            ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.25, BORDER),
        ]))
        story.append(af_tbl)
        story.append(Paragraph(
            "Stage-1 detector emits 'aircraft-fixed-wing'; stage-2 yolo11n-cls trained on "
            "MAR20 (89.03% top-1, 99.32% top-5) refines to specific airframe.",
            s["muted"],
        ))

    # ── R3: OOD-flagged section ──────────────────────────────────────────
    ood_dets: list = []
    for d in detections:
        ex = json.loads(d.extras_json) if d.extras_json else {}
        if ex.get("ood_flag"):
            ood_dets.append((d, ex))
    if ood_dets:
        story.append(Paragraph(f"Out-of-Distribution Gatekeeper · {len(ood_dets)} detection(s) flagged", s["h2"]))
        story.append(Paragraph(
            "Detections whose confidence × aspect-ratio × edge-density signals exceed the OOD threshold (0.55). "
            "Frontend renders these grey-with-?, the system showing it knew it didn't know.",
            s["muted"],
        ))
        story.append(Spacer(1, 3))
        ood_rows = [["Det ID", "Stage-1 class", "Conf", "OOD score", "Reasons"]]
        for d, ex in ood_dets[:25]:
            ood_rows.append([
                f"#{d.id}",
                d.class_name,
                f"{d.confidence:.2f}",
                f"{ex.get('ood_score', 0):.3f}",
                ", ".join(ex.get("ood_reasons", []))[:50],
            ])
        ood_tbl = Table(ood_rows, colWidths=[18 * mm, 38 * mm, 16 * mm, 22 * mm, 76 * mm])
        ood_tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), PANEL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Courier"),
            ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("GRID", (0, 0), (-1, -1), 0.2, BORDER),
        ]))
        story.append(ood_tbl)

    # Top threats
    if alerts:
        story.append(Paragraph(f"Top {min(15, len(alerts))} Threat Alerts (ranked by score)", s["h2"]))
        det_map = {d.id: d for d in detections}

        for rank, a in enumerate(alerts[:15], start=1):
            det = det_map.get(a.detection_id)
            breakdown = json.loads(a.score_breakdown_json) if a.score_breakdown_json else {}
            threat_col = _threat_color(a.threat_score)
            status_str = a.status.value if hasattr(a.status, "value") else str(a.status)

            # One row per alert with a narrative line below
            row1 = [
                Paragraph(f'<b>#{rank}</b>', s["body"]),
                Paragraph(f'<font color="{threat_col.hexval()}"><b>{a.threat_score:.3f}</b></font>', s["body"]),
                Paragraph(det.class_name if det else "?", s["body"]),
                Paragraph(f'{det.confidence:.2f}' if det else "—", s["mono"]),
                Paragraph(
                    f'{breakdown.get("distance_km", 0):.2f} km · {breakdown.get("nearest_asset") or "—"}'
                    if breakdown.get("distance_km") is not None else "—",
                    s["mono"],
                ),
                Paragraph(
                    f'<b>{status_str}</b>' if status_str != "pending" else status_str,
                    s["body"],
                ),
            ]
            narrative_line = [a.narrative or "(no narrative)", "", "", "", "", ""]

            alert_tbl = Table(
                [row1, narrative_line],
                colWidths=[12 * mm, 18 * mm, 40 * mm, 15 * mm, 55 * mm, 30 * mm],
            )
            alert_tbl.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("TOPPADDING", (0, 1), (-1, 1), 0),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
                ("SPAN", (0, 1), (-1, 1)),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Oblique"),
                ("TEXTCOLOR", (0, 1), (-1, 1), MUTED),
                ("LINEBELOW", (0, 1), (-1, 1), 0.25, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(alert_tbl)

        if len(alerts) > 15:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<i>... {len(alerts) - 15} additional lower-ranked alerts omitted.</i>",
                s["muted"],
            ))

    # Audit events
    if events:
        story.append(Paragraph("Audit Trail", s["h2"]))
        audit_rows = [["Timestamp (UTC)", "Operator", "Event", "Detail"]]
        for e in events:
            detail = json.dumps(e.payload_json, separators=(",", ":"))[:80] if e.payload_json else ""
            event_type = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
            audit_rows.append([
                _fmt_ts(e.created_at),
                e.operator_id or "system",
                event_type,
                detail,
            ])
        audit_tbl = Table(audit_rows, colWidths=[35 * mm, 22 * mm, 38 * mm, 75 * mm])
        audit_tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), PANEL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("FONTNAME", (0, 1), (-1, -1), "Courier"),
            ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("GRID", (0, 0), (-1, -1), 0.2, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(audit_tbl)

    # ── R3: Audit chain validation cert ──────────────────────────────────
    story.append(Paragraph("Audit Chain Validation", s["h2"]))
    try:
        from app.services.audit import verify_chain
        chain_result = verify_chain(db)
        chain_ok = chain_result.get("ok", False)
        chain_checked = chain_result.get("checked", 0)
        chain_break = chain_result.get("broken_at_id")
        cert_rows = [
            ["Chain status", "VERIFIED ✓" if chain_ok else f"BROKEN at #{chain_break}"],
            ["Rows checked", f"{chain_checked} audit events"],
            ["Algorithm",   "SHA-256 (prev_hash || canonical_json(row))"],
            ["Genesis",     "0" * 64],
        ]
        cert_tbl = Table(cert_rows, colWidths=[40 * mm, 130 * mm])
        cert_tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Courier"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("TEXTCOLOR", (1, 0), (1, 0), THREAT_LOW if chain_ok else THREAT_CRIT),
            ("TEXTCOLOR", (1, 1), (1, -1), TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, -1), 0.2, BORDER),
        ]))
        story.append(cert_tbl)
    except Exception as exc:
        story.append(Paragraph(f"<i>Chain verification unavailable: {exc}</i>", s["muted"]))

    # ── R3: Federated participation log (if any) ─────────────────────────
    try:
        import os
        from pathlib import Path as _P
        from app.config import FEDERATED_LOG
        fed_log = _P(os.environ.get("ASTRA_FEDERATED_LOG") or FEDERATED_LOG)
        if fed_log.exists():
            recs = []
            for line in fed_log.read_text(encoding="utf-8").splitlines()[-200:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
            cfg_rec = next((r for r in recs if r.get("kind") == "server_start"), None)
            agg_recs = [r for r in recs if r.get("kind") == "aggregation"]
            fg_recs = [r for r in recs if r.get("kind") == "foolsgold"]
            if cfg_rec and agg_recs:
                story.append(Paragraph("Federated Participation (FedAvg + FoolsGold)", s["h2"]))
                last = agg_recs[-1]
                last_acc = (last.get("global_eval") or {}).get("accuracy")
                fed_rows = [
                    ["Task",          str(cfg_rec.get("task", "—"))],
                    ["Clients",       ", ".join(cfg_rec.get("client_ids", []))],
                    ["Rounds done",   str(last.get("round", "—"))],
                    ["Final accuracy", f"{last_acc * 100:.1f}%" if isinstance(last_acc, (int, float)) else "—"],
                ]
                if fg_recs:
                    last_fg = fg_recs[-1]
                    quarantined = [c for c, d in last_fg.get("diag", {}).items() if d.get("flagged")]
                    fed_rows.append(["FoolsGold quarantined", ", ".join(quarantined) if quarantined else "(none)"])
                fed_tbl = Table(fed_rows, colWidths=[40 * mm, 130 * mm])
                fed_tbl.setStyle(TableStyle([
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Courier"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                    ("TEXTCOLOR", (1, 0), (1, -1), TEXT),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.2, BORDER),
                ]))
                story.append(fed_tbl)
    except Exception:
        pass

    # Footer — integrity hash
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.25, color=BORDER))
    story.append(Spacer(1, 3))

    # Compute integrity hash over the meaningful content
    hash_body = json.dumps({
        "mission_id": mission.id,
        "name": mission.name,
        "created_at": mission.created_at.isoformat(),
        "detections": len(detections),
        "alerts": len(alerts),
        "class_counts": cls_counts,
        "airframe_counts": airframe_counts,
        "ood_count": len(ood_dets),
        "status_counts": status_counts,
    }, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(hash_body).hexdigest()

    story.append(Paragraph(
        f"<b>Integrity:</b> SHA-256 = <font face='Courier'>{digest}</font>",
        s["muted"],
    ))
    story.append(Paragraph(
        "Generated by ASTRA · Aerial Surveillance &amp; Threat Recognition · "
        f"Report timestamp {_fmt_ts(datetime.now(timezone.utc))}",
        s["muted"],
    ))

    doc.build(story)
    return buffer.getvalue()
