from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, AuditEventType


def log_event(
    db: Session,
    event_type: AuditEventType,
    *,
    operator_id: str | None = None,
    mission_id: int | None = None,
    alert_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an immutable audit event. Caller is responsible for commit."""
    event = AuditEvent(
        event_type=event_type,
        operator_id=operator_id,
        mission_id=mission_id,
        alert_id=alert_id,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event
