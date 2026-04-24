from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEventType, Mission
from app.db.session import get_db
from app.schemas import AoiCorners, MissionOut
from app.services.audit import log_event
from app.services.geo_extract import extract_gps, synthesize_aoi
from app.services.pipeline import process_mission

router = APIRouter(prefix="/ingest", tags=["ingest"])

ALLOWED_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".jpg", ".jpeg", ".png"}


@router.post("", response_model=MissionOut)
async def create_mission(
    background: BackgroundTasks,
    name: str = Form(..., min_length=1, max_length=128),
    aoi_corners: str | None = Form(None, description="JSON-encoded AoiCorners"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> MissionOut:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    corners_obj: AoiCorners | None = None
    aoi_source = "default"  # default | explicit | gps-exif

    if aoi_corners:
        try:
            corners_obj = AoiCorners.model_validate_json(aoi_corners)
            aoi_source = "explicit"
        except Exception as exc:
            raise HTTPException(400, f"Invalid aoi_corners: {exc}") from exc

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.uploads_dir / f"{name}{suffix}"

    # Read the file once: we may need bytes for EXIF extraction AND we need
    # to write them to disk. Stream-copy is cheaper but we want both.
    raw = await file.read()
    with dest.open("wb") as out:
        out.write(raw)

    # If caller didn't supply AOI explicitly, try EXIF GPS.
    gps_point: tuple[float, float] | None = None
    if corners_obj is None and suffix in {".jpg", ".jpeg", ".png"}:
        gps_point = extract_gps(raw)
        if gps_point is not None:
            lat, lon = gps_point
            corners_obj = AoiCorners.model_validate(synthesize_aoi(lat, lon, size_m=400.0))
            aoi_source = "gps-exif"

    # Final fallback: if we STILL have no AOI, use a default Bangalore box
    # so the Map page isn't empty. (Matches FOB Delta / friendly_assets.)
    if corners_obj is None:
        corners_obj = AoiCorners.model_validate({
            "top_left":     [12.9750, 77.5900],
            "top_right":    [12.9750, 77.6000],
            "bottom_right": [12.9650, 77.6000],
            "bottom_left":  [12.9650, 77.5900],
        })
        aoi_source = "default"

    mission = Mission(
        name=name,
        source_path=str(dest),
        aoi_corners_json=corners_obj.model_dump_json() if corners_obj else None,
    )
    db.add(mission)
    db.flush()

    log_event(
        db,
        AuditEventType.INGEST_STARTED,
        mission_id=mission.id,
        payload={
            "filename": file.filename,
            "size_bytes": dest.stat().st_size,
            "aoi_source": aoi_source,
            "gps_point": list(gps_point) if gps_point else None,
        },
    )
    db.commit()
    db.refresh(mission)

    # Fire-and-forget inference pipeline. Runs in-process after the response
    # is sent — see backend/app/services/pipeline.py.
    background.add_task(process_mission, mission.id)

    out = MissionOut.model_validate(mission)
    # Attach ingest-time metadata so the Mission page can show 'GPS detected'
    out.aoi_source = aoi_source  # type: ignore[assignment]
    out.gps_point = gps_point  # type: ignore[assignment]
    return out


@router.get("/{mission_id}", response_model=MissionOut)
def get_mission(mission_id: int, db: Session = Depends(get_db)) -> MissionOut:
    mission = db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    return MissionOut.model_validate(mission)


@router.get("", response_model=list[MissionOut])
def list_missions(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[MissionOut]:
    """Recent missions, newest first. Used by the Map page's mission selector."""
    stmt = select(Mission).order_by(Mission.created_at.desc()).limit(limit)
    return [MissionOut.model_validate(m) for m in db.execute(stmt).scalars().all()]
