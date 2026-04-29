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


@router.get("/verify-row/{row_id}")
def verify_audit_row(row_id: int, db: Session = Depends(get_db)) -> dict:
    """Walk the chain from genesis to (and including) row_id only.
    Cheap form of verify_chain that also returns that row's prev_hash and
    row_hash so the UI can render them."""
    if row_id < 1:
        raise HTTPException(400, "row_id must be >= 1")
    return verify_row(db, row_id)


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
    db: Session = Depends(get_db),
) -> Response:
    """Generate a self-contained certificate PDF for the [since, until]
    window. Either bound may be omitted (open-ended). Always renders
    chronologically (ascending by id) so the start_hash / end_hash
    bookend the range correctly.
    """
    stmt = select(AuditEvent).order_by(AuditEvent.id.asc())
    if since is not None:
        stmt = stmt.where(AuditEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditEvent.created_at <= until)
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
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="astra-audit-range-cert.pdf"',
        },
    )
