"""
Mission diff / change detection.

Given two mission IDs (an "earlier" baseline and a "later" comparison), return
how the world changed: which detections are NEW (appeared in later but not
earlier), which are GONE (in earlier but not later), and which MOVED (same
class, similar location, different position).

Matching strategy:
  We match earlier → later detections that share a class AND lie within a
  configurable lat/lon radius (default 50 m). Greedy nearest-neighbour:
  for each earlier detection, find the closest later detection of the same
  class within the radius; pair them.

  - matched within move_threshold_m → "stable" (not in output)
  - matched but moved further than move_threshold_m → "moved"
  - earlier-side leftover → "removed"
  - later-side leftover → "added"

Returns a JSON payload the React MissionDiff page can render.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Detection, Mission
from app.db.session import SessionLocal
from app.fusion.georef import haversine_km

router = APIRouter(prefix="/diff", tags=["diff"])


class DiffRequest(BaseModel):
    earlier_mission_id: int
    later_mission_id: int
    match_radius_m: float = 50.0     # how close must same-class objects be to be the "same" object
    move_threshold_m: float = 15.0   # below this, treat as "stable"; above, "moved"


class DiffPoint(BaseModel):
    detection_id: int
    class_name: str
    confidence: float
    lat: float
    lon: float
    track_id: int | None = None


class MovedPair(BaseModel):
    earlier: DiffPoint
    later: DiffPoint
    distance_m: float


class DiffResponse(BaseModel):
    earlier: dict   # {mission_id, name, created_at, geo_count}
    later: dict
    added: list[DiffPoint]
    removed: list[DiffPoint]
    moved: list[MovedPair]
    stable_count: int
    summary_text: str


def _to_point(d: Detection) -> DiffPoint:
    return DiffPoint(
        detection_id=d.id,
        class_name=d.class_name,
        confidence=d.confidence,
        lat=d.lat or 0.0,
        lon=d.lon or 0.0,
        track_id=d.track_id,
    )


def _mission_summary(db: Session, mid: int) -> tuple[Mission, list[Detection]]:
    m = db.get(Mission, mid)
    if not m:
        raise HTTPException(404, f"mission {mid} not found")
    geo_dets = list(
        db.execute(
            select(Detection)
            .where(Detection.mission_id == mid)
            .where(Detection.lat.is_not(None))
            .where(Detection.lon.is_not(None))
        ).scalars().all()
    )
    return m, geo_dets


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_km((lat1, lon1), (lat2, lon2)) * 1000.0


@router.post("", response_model=DiffResponse)
def compute_diff(req: DiffRequest) -> DiffResponse:
    db: Session = SessionLocal()
    try:
        m_old, dets_old = _mission_summary(db, req.earlier_mission_id)
        m_new, dets_new = _mission_summary(db, req.later_mission_id)

        # Index later detections by class for cheaper search.
        new_by_class: dict[str, list[Detection]] = {}
        for d in dets_new:
            new_by_class.setdefault(d.class_name, []).append(d)
        consumed_new: set[int] = set()

        moved: list[MovedPair] = []
        removed: list[DiffPoint] = []
        stable_count = 0

        for old in dets_old:
            candidates = [c for c in new_by_class.get(old.class_name, []) if c.id not in consumed_new]
            if not candidates:
                removed.append(_to_point(old))
                continue
            # Greedy nearest-neighbour by haversine distance
            best, best_dist = None, float("inf")
            for c in candidates:
                d = _haversine_m(old.lat, old.lon, c.lat, c.lon)
                if d < best_dist:
                    best, best_dist = c, d
            if best is None or best_dist > req.match_radius_m:
                removed.append(_to_point(old))
                continue
            consumed_new.add(best.id)
            if best_dist <= req.move_threshold_m:
                stable_count += 1
            else:
                moved.append(MovedPair(
                    earlier=_to_point(old),
                    later=_to_point(best),
                    distance_m=round(best_dist, 2),
                ))

        # Anything in `dets_new` not consumed = added
        added = [_to_point(d) for d in dets_new if d.id not in consumed_new]

        # Human-readable summary
        bits = []
        if added:
            bits.append(f"{len(added)} new")
        if removed:
            bits.append(f"{len(removed)} gone")
        if moved:
            bits.append(f"{len(moved)} moved")
        if not bits:
            summary = f"No change — {stable_count} objects in same position."
        else:
            summary = f"{', '.join(bits)} ({stable_count} unchanged)."

        def _summary(m: Mission, dets: list[Detection]) -> dict:
            return {
                "mission_id": m.id,
                "name": m.name,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "geo_count": len(dets),
            }

        return DiffResponse(
            earlier=_summary(m_old, dets_old),
            later=_summary(m_new, dets_new),
            added=added,
            removed=removed,
            moved=moved,
            stable_count=stable_count,
            summary_text=summary,
        )
    finally:
        db.close()
