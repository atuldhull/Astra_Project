from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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


class TrackPoint(BaseModel):
    frame_index: int
    frame_timestamp_ms: int
    lat: float | None
    lon: float | None
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


class TrackOut(BaseModel):
    track_id: int
    class_id: int
    class_name: str
    point_count: int
    avg_confidence: float
    points: list[TrackPoint]


# Same /tracks path lives under detections namespace for route simplicity
tracks_router = APIRouter(prefix="/tracks", tags=["tracks"])


@tracks_router.get("", response_model=list[TrackOut])
def list_tracks(
    mission_id: int = Query(..., description="Filter by mission"),
    db: Session = Depends(get_db),
) -> list[TrackOut]:
    """Return detections for a mission grouped by track_id, with points
    sorted chronologically. Only tracks with >=2 points are useful for
    visualization (single-point tracks are just detections)."""
    stmt = (
        select(Detection)
        .where(Detection.mission_id == mission_id)
        .where(Detection.track_id.is_not(None))
        .order_by(Detection.track_id.asc(), Detection.frame_index.asc())
    )
    rows = db.execute(stmt).scalars().all()

    groups: dict[int, list[Detection]] = {}
    for d in rows:
        if d.track_id is None:
            continue
        groups.setdefault(d.track_id, []).append(d)

    out: list[TrackOut] = []
    for tid, items in groups.items():
        # Prefer the majority class across the track (track may misclassify on a frame)
        cls_counts: dict[tuple[int, str], int] = {}
        for d in items:
            key = (d.class_id, d.class_name)
            cls_counts[key] = cls_counts.get(key, 0) + 1
        best_class = max(cls_counts.items(), key=lambda kv: kv[1])[0]

        avg_conf = sum(d.confidence for d in items) / len(items)
        out.append(TrackOut(
            track_id=tid,
            class_id=best_class[0],
            class_name=best_class[1],
            point_count=len(items),
            avg_confidence=round(avg_conf, 4),
            points=[
                TrackPoint(
                    frame_index=d.frame_index,
                    frame_timestamp_ms=d.frame_timestamp_ms,
                    lat=d.lat, lon=d.lon,
                    x1=d.x1, y1=d.y1, x2=d.x2, y2=d.y2,
                    confidence=d.confidence,
                )
                for d in items
            ],
        ))
    # Sort by point count desc so biggest tracks come first in UI
    out.sort(key=lambda t: -t.point_count)
    return out
