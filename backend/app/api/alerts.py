from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Alert, AlertStatus, AuditEventType
from app.db.session import get_db
from app.schemas import AlertActionIn, AlertOut, ScoreBreakdown
from app.services.audit import log_event

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _to_out(alert: Alert) -> AlertOut:
    breakdown = ScoreBreakdown.model_validate(json.loads(alert.score_breakdown_json))
    return AlertOut(
        id=alert.id,
        mission_id=alert.mission_id,
        detection_id=alert.detection_id,
        threat_score=alert.threat_score,
        score_breakdown=breakdown,
        status=alert.status.value,
        operator_id=alert.operator_id,
        narrative=alert.narrative,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


@router.get("", response_model=list[AlertOut])
def list_alerts(
    mission_id: int | None = Query(None),
    status: AlertStatus | None = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    stmt = select(Alert).where(Alert.threat_score >= min_score)
    if mission_id is not None:
        stmt = stmt.where(Alert.mission_id == mission_id)
    if status is not None:
        stmt = stmt.where(Alert.status == status)
    stmt = stmt.order_by(Alert.threat_score.desc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [_to_out(r) for r in rows]


@router.patch("/{alert_id}", response_model=AlertOut)
def act_on_alert(
    alert_id: int,
    action: AlertActionIn,
    db: Session = Depends(get_db),
) -> AlertOut:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")

    event_type_map = {
        "confirm": (AlertStatus.CONFIRMED, AuditEventType.ALERT_CONFIRMED),
        "reject": (AlertStatus.REJECTED, AuditEventType.ALERT_REJECTED),
        "reclassify": (alert.status, AuditEventType.ALERT_RECLASSIFIED),
        "escalate": (AlertStatus.ESCALATED, AuditEventType.ALERT_ESCALATED),
    }
    new_status, event_type = event_type_map[action.action]
    alert.status = new_status
    alert.operator_id = action.operator_id

    log_event(
        db,
        event_type,
        operator_id=action.operator_id,
        mission_id=alert.mission_id,
        alert_id=alert.id,
        payload={
            "action": action.action,
            "new_class_id": action.new_class_id,
            "reason": action.reason,
        },
    )
    db.commit()
    db.refresh(alert)
    return _to_out(alert)
