from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Detection
from app.db.session import get_db
from app.schemas import DetectionOut

router = APIRouter(prefix="/detections", tags=["detections"])


@router.get("", response_model=list[DetectionOut])
def list_detections(
    mission_id: int | None = Query(None),
    class_id: int | None = Query(None),
    track_id: int | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[DetectionOut]:
    stmt = select(Detection).order_by(Detection.created_at.desc()).limit(limit)
    if mission_id is not None:
        stmt = stmt.where(Detection.mission_id == mission_id)
    if class_id is not None:
        stmt = stmt.where(Detection.class_id == class_id)
    if track_id is not None:
        stmt = stmt.where(Detection.track_id == track_id)
    rows = db.execute(stmt).scalars().all()
    return [DetectionOut.model_validate(r) for r in rows]
