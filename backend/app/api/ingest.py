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
    if aoi_corners:
        try:
            corners_obj = AoiCorners.model_validate_json(aoi_corners)
        except Exception as exc:
            raise HTTPException(400, f"Invalid aoi_corners: {exc}") from exc

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.uploads_dir / f"{name}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

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
        payload={"filename": file.filename, "size_bytes": dest.stat().st_size},
    )
    db.commit()
    db.refresh(mission)

    # Fire-and-forget inference pipeline. Runs in-process after the response
    # is sent — see backend/app/services/pipeline.py.
    background.add_task(process_mission, mission.id)

    return MissionOut.model_validate(mission)


@router.get("/{mission_id}", response_model=MissionOut)
def get_mission(mission_id: int, db: Session = Depends(get_db)) -> MissionOut:
    mission = db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(404, "Mission not found")
    return MissionOut.model_validate(mission)
