from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, AuditEventType
from app.db.session import get_db
from app.schemas import AuditEventOut
from app.services.audit import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
def list_events(
    event_type: AuditEventType | None = Query(None),
    operator_id: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[AuditEventOut]:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if event_type is not None:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if operator_id is not None:
        stmt = stmt.where(AuditEvent.operator_id == operator_id)
    if since is not None:
        stmt = stmt.where(AuditEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditEvent.created_at <= until)
    rows = db.execute(stmt).scalars().all()
    return [AuditEventOut.model_validate(r) for r in rows]


@router.get("/verify")
def verify_audit_chain(db: Session = Depends(get_db)) -> dict:
    """Walk the entire audit log and confirm SHA-256 hash-chain integrity.
    Frontend Audit page renders the result as a green/red badge."""
    return verify_chain(db)
