"""
/audit — append-only event log + chain verification + range certificates.

Endpoints:
  GET  /audit                       list events with filters
  GET  /audit/verify                walk full chain
  GET  /audit/verify-row/{row_id}   walk chain to a single row
  GET  /audit/range-cert            PDF certificate for a [since, until] window
  GET  /audit/operator-activity     per-operator histogram inside a window
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, AuditEventType
from app.db.session import get_db
from app.schemas import AuditEventOut
from app.services.audit import verify_chain, verify_row
from app.services.range_cert import render_range_cert

router = APIRouter(prefix="/audit", tags=["audit"])


# ── Filter parsing ───────────────────────────────────────────────────

_VALID_EVENT_TYPES: set[str] = {e.value for e in AuditEventType}


def _parse_event_types(raw: str | None) -> list[AuditEventType] | None:
    """Parse comma-separated event_types; reject unknowns. Returns None
    when the param is absent so the caller can skip the filter."""
    if not raw:
        return None
    out: list[AuditEventType] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok not in _VALID_EVENT_TYPES:
            raise HTTPException(400, f"unknown event_type: {tok}")
        out.append(AuditEventType(tok))
    return out or None


# ── List ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[AuditEventOut])
def list_events(
    event_type: AuditEventType | None = Query(None, description="legacy single-type filter"),
    event_types: str | None = Query(None, description="comma-separated AuditEventType values"),
    operator_id: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    alert_id: int | None = Query(None, description="filter to events tied to one alert"),
    mission_id: int | None = Query(None, description="optional mission filter"),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[AuditEventOut]:
    """Most recent events first. event_types (multi) takes precedence over
    event_type (single) when both are present."""
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    multi = _parse_event_types(event_types)
    if multi:
        stmt = stmt.where(AuditEvent.event_type.in_(multi))
    elif event_type is not None:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if operator_id is not None:
        stmt = stmt.where(AuditEvent.operator_id == operator_id)
    if alert_id is not None:
        stmt = stmt.where(AuditEvent.alert_id == alert_id)
    if mission_id is not None:
        stmt = stmt.where(AuditEvent.mission_id == mission_id)
    if since is not None:
        stmt = stmt.where(AuditEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditEvent.created_at <= until)
    rows = db.execute(stmt).scalars().all()
    return [AuditEventOut.model_validate(r) for r in rows]


# ── Verify ───────────────────────────────────────────────────────────

@router.get("/verify")
def verify_audit_chain(db: Session = Depends(get_db)) -> dict:
    return verify_chain(db)


@router.get("/latest-by-alert")
def latest_by_alert(
    alert_ids: str = Query(..., description="comma-separated alert ids"),
    db: Session = Depends(get_db),
) -> dict:
    """batch lookup of the latest audit row id per alert id.
    Used by /alerts to pre-fetch verify-target row ids on page load
    instead of firing 50 individual /audit?alert_id=N requests when the
    operator hovers each badge."""
    try:
        ids = [int(x) for x in alert_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "alert_ids must be comma-separated integers")
    if not ids:
        return {"by_alert": {}}
    if len(ids) > 200:
        raise HTTPException(400, "too many alert ids; max 200")
    # max(id) per alert in one query.
    from sqlalchemy import func as _f
    rows = db.execute(
        select(AuditEvent.alert_id, _f.max(AuditEvent.id))
        .where(AuditEvent.alert_id.in_(ids))
        .group_by(AuditEvent.alert_id)
    ).all()
    out: dict[str, int | None] = {str(i): None for i in ids}
    for alert_id, max_row in rows:
        out[str(alert_id)] = int(max_row) if max_row else None
    return {"by_alert": out}


@router.get("/verify-row/{row_id}")
def verify_audit_row(row_id: int, db: Session = Depends(get_db)) -> dict:
    """Walk the chain from genesis to (and including) row_id only.
    Cheap form of verify_chain that also returns that row's prev_hash and
    row_hash so the UI can render them."""
    if row_id < 1:
        raise HTTPException(400, "row_id must be >= 1")
    return verify_row(db, row_id)


# ── Mission snapshot ──────────────────────────────────────────

@router.get("/snapshot")
def audit_snapshot(
    mission_id: int = Query(..., description="mission to snapshot"),
    until_ts: datetime | None = Query(None, description="cutoff (inclusive); default = now"),
    db: Session = Depends(get_db),
) -> dict:
    """Return the audit-chain state *as of* `until_ts` for one mission.

    Used by the Mission Replay Scrubber. When the operator scrubs
    to time T, the UI fetches:
      • events: the mission's audit rows where created_at <= T
      • tip:    the LATEST audit row (mission-scoped or otherwise) at
                or before T — that's the chain head the system would
                report at that moment
      • witnesses: mesh_witnesses whose witnessed_at <= T, joined to
                   the events in this snapshot

    The frontend renders this as a "ledger drawer" + "tip-as-of-T" badge
    + a witness pulse animation when scrubbing past a witness event.
    """
    from app.db.models import MeshWitness  # local import to avoid cycle in tests

    until = until_ts or datetime.now(timezone.utc)

    # Mission-scoped events ≤ T
    ev_stmt = (
        select(AuditEvent)
        .where(AuditEvent.mission_id == mission_id)
        .where(AuditEvent.created_at <= until)
        .order_by(AuditEvent.id.asc())
    )
    events = db.execute(ev_stmt).scalars().all()

    # Tip-as-of-T: the latest audit row (any mission) ≤ T. The tip the
    # system would have reported at exactly that moment.
    tip_stmt = (
        select(AuditEvent.id, AuditEvent.row_hash, AuditEvent.created_at)
        .where(AuditEvent.created_at <= until)
        .order_by(AuditEvent.id.desc()).limit(1)
    )
    tip_row = db.execute(tip_stmt).first()

    # Witnesses pinned to any event in this snapshot, witnessed by ≤ T.
    event_ids = [e.id for e in events]
    witnesses: list[dict] = []
    if event_ids:
        w_stmt = (
            select(MeshWitness)
            .where(MeshWitness.audit_row_id.in_(event_ids))
            .where(MeshWitness.witnessed_at <= until)
            .order_by(MeshWitness.witnessed_at.asc())
        )
        for w in db.execute(w_stmt).scalars().all():
            witnesses.append({
                "id": w.id,
                "peer_id": w.peer_id,
                "audit_row_id": w.audit_row_id,
                "row_hash": w.row_hash,
                "witnessed_at": w.witnessed_at.isoformat() if w.witnessed_at else None,
            })

    return {
        "mission_id": mission_id,
        "until_ts": until.isoformat(),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                "operator_id": e.operator_id,
                "mission_id": e.mission_id,
                "alert_id": e.alert_id,
                "row_hash": e.row_hash,
                "prev_hash": e.prev_hash,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "tip": {
            "id": int(tip_row[0]) if tip_row else None,
            "row_hash": tip_row[1] if tip_row else None,
            "created_at": tip_row[2].isoformat() if tip_row and tip_row[2] else None,
        },
        "witnesses": witnesses,
    }


# ── Operator activity (histogram inside a window) ────────────────────

@router.get("/operator-activity")
def operator_activity(
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Per-operator counts inside [since, until]. System events
    (operator_id IS NULL) are not in the operator list but are returned
    as a separate top-level field so the rail can render
    "system events: N" beneath the human operators.
    """
    stmt = select(AuditEvent)
    if since is not None:
        stmt = stmt.where(AuditEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditEvent.created_at <= until)
    rows = db.execute(stmt).scalars().all()

    by_op: dict[str, Counter] = defaultdict(Counter)
    system_events = 0
    for r in rows:
        et = r.event_type.value if hasattr(r.event_type, "value") else str(r.event_type)
        if r.operator_id:
            by_op[r.operator_id][et] += 1
        else:
            system_events += 1

    operators = []
    for op_id, ctr in by_op.items():
        operators.append({
            "operator_id": op_id,
            "total": int(sum(ctr.values())),
            "by_event_type": dict(ctr),
        })
    operators.sort(key=lambda x: -x["total"])

    return {
        "since": since.isoformat() if since else None,
        "until": until.isoformat() if until else None,
        "operators": operators,
        "system_events": system_events,
        "total": len(rows),
    }


# ── Range certificate (PDF) ──────────────────────────────────────────

@router.get("/range-cert")
def audit_range_cert(
    since: Optional[datetime] = Query(None, description="inclusive lower bound"),
    until: Optional[datetime] = Query(None, description="inclusive upper bound"),
    mission_id: Optional[int] = Query(None, description="optional mission filter — D4.6 replay-clip"),
    db: Session = Depends(get_db),
) -> Response:
    """Generate a self-contained certificate PDF for the [since, until]
    window. Either bound may be omitted (open-ended). Always renders
    chronologically (ascending by id) so the start_hash / end_hash
    bookend the range correctly.

    D4.6: passing mission_id narrows the certificate to a single
    mission's events — used as the "Export replay clip" download from
    the Mission Replay Scrubber.
    """
    stmt = select(AuditEvent).order_by(AuditEvent.id.asc())
    if since is not None:
        stmt = stmt.where(AuditEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditEvent.created_at <= until)
    if mission_id is not None:
        stmt = stmt.where(AuditEvent.mission_id == mission_id)
    rows = db.execute(stmt).scalars().all()
    if not rows:
        raise HTTPException(404, "no events in this window")

    start_hash = rows[0].row_hash
    end_hash = rows[-1].row_hash
    by_event_type: dict[str, int] = {}
    for r in rows:
        et = r.event_type.value if hasattr(r.event_type, "value") else str(r.event_type)
        by_event_type[et] = by_event_type.get(et, 0) + 1

    # Pubkey fingerprint — same one used for detection signatures.
    try:
        from app.services.provenance import public_key_fingerprint
        fp = public_key_fingerprint()
    except Exception:
        fp = None

    pdf = render_range_cert(
        since_iso=since.astimezone(timezone.utc).isoformat() if since else None,
        until_iso=until.astimezone(timezone.utc).isoformat() if until else None,
        rows=rows,
        start_hash=start_hash,
        end_hash=end_hash,
        pubkey_fingerprint=fp,
        by_event_type=by_event_type,
        generated_by="astra-backend",
    )
    fname = (
        f"astra-replay-clip-mission-{mission_id}.pdf"
        if mission_id is not None
        else "astra-audit-range-cert.pdf"
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{fname}"',
        },
    )
