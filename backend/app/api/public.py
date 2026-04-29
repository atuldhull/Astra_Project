"""
/public — citizen-submission ingest with manual-pin triage fallback.

POST /public/submit            multipart file + reporter_id + caption?
POST /public/{mission_id}/pin  operator drops manual pin on a no-GPS mission
GET  /public/triage            operator queue (awaiting-pin missions)
GET  /public/recent            last N public reports with status

Behaviour:
  * EXIF GPS present → mission goes through the same pipeline as /ingest
    (aoi_source=public-gps).
  * No GPS → mission lands in triage with extras_json={"status":"awaiting_pin"}.
    Pipeline runs only after operator drops a pin via POST /public/{id}/pin.

Audit chain captures:
  * public_report_submitted  on every /submit
  * public_report_pinned     on every /pin
The chain-of-custody is intact whether the report came from a citizen or
an operator.
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEventType, Mission
from app.db.session import get_db
from app.schemas import AoiCorners, MissionOut
from app.services.audit import log_event
from app.services.geo_extract import extract_gps, synthesize_aoi
from app.services.pipeline import process_mission

router = APIRouter(prefix="/public", tags=["public"])

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _public_uploads_dir() -> Path:
    d = settings.uploads_dir / "public"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Schemas ────────────────────────────────────────────────────────────

class PinIn(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    operator_id: str = Field(..., min_length=1, max_length=64)


class PublicSubmitOut(BaseModel):
    mission_id: int
    has_gps: bool
    aoi_source: str
    name: str


class TriageRowOut(BaseModel):
    mission_id: int
    name: str
    reporter_id: str | None
    source_path: str
    created_at: str
    caption: str | None = None


class RecentRowOut(BaseModel):
    mission_id: int
    name: str
    reporter_id: str | None
    aoi_source: str | None
    status: str       # "awaiting" | "pinned" | "processing" | "complete"
    created_at: str


# ── Helpers ────────────────────────────────────────────────────────────

def _extras(mission: Mission) -> dict:
    if not mission.extras_json:
        return {}
    try:
        return json.loads(mission.extras_json)
    except Exception:
        return {}


def _set_extras(mission: Mission, **kwargs) -> None:
    cur = _extras(mission)
    cur.update(kwargs)
    mission.extras_json = json.dumps(cur)


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post("/submit", response_model=PublicSubmitOut)
async def submit(
    background: BackgroundTasks,
    reporter_id: str = Form(..., min_length=1, max_length=64),
    caption: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> PublicSubmitOut:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    raw = await file.read()
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(3)
    dest = _public_uploads_dir() / f"{ts}-{rand}{suffix}"
    dest.write_bytes(raw)

    name = f"PUBREP-{ts}-{rand}"

    # Try EXIF GPS first.
    gps_point = extract_gps(raw)
    if gps_point is not None:
        lat, lon = gps_point
        corners = AoiCorners.model_validate(synthesize_aoi(lat, lon, size_m=400.0))
        mission = Mission(
            name=name,
            source_path=str(dest),
            aoi_corners_json=corners.model_dump_json(),
            source_kind="public-report",
            reporter_id=reporter_id,
        )
        if caption:
            _set_extras(mission, caption=caption[:500])
        _set_extras(mission, aoi_source="public-gps", gps_point=[lat, lon])
        db.add(mission)
        db.flush()

        log_event(
            db, AuditEventType.PUBLIC_REPORT_SUBMITTED,
            mission_id=mission.id,
            payload={
                "reporter_id": reporter_id,
                "has_gps": True,
                "aoi_source": "public-gps",
                "gps_point": [lat, lon],
                "filename": file.filename,
                "size_bytes": dest.stat().st_size,
            },
        )
        db.commit()
        db.refresh(mission)

        # Same pipeline path as /ingest, fire-and-forget.
        background.add_task(process_mission, mission.id)
        return PublicSubmitOut(mission_id=mission.id, has_gps=True, aoi_source="public-gps", name=name)

    # No GPS — park in triage.
    mission = Mission(
        name=name,
        source_path=str(dest),
        aoi_corners_json=None,
        source_kind="public-report",
        reporter_id=reporter_id,
    )
    _set_extras(
        mission,
        status="awaiting_pin",
        aoi_source="unknown",
    )
    if caption:
        _set_extras(mission, caption=caption[:500])
    db.add(mission)
    db.flush()

    log_event(
        db, AuditEventType.PUBLIC_REPORT_SUBMITTED,
        mission_id=mission.id,
        payload={
            "reporter_id": reporter_id,
            "has_gps": False,
            "aoi_source": "unknown",
            "filename": file.filename,
            "size_bytes": dest.stat().st_size,
        },
    )
    db.commit()
    db.refresh(mission)
    return PublicSubmitOut(mission_id=mission.id, has_gps=False, aoi_source="unknown", name=name)


@router.post("/{mission_id}/pin", response_model=MissionOut)
async def pin(
    mission_id: int,
    body: PinIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MissionOut:
    m = db.get(Mission, mission_id)
    if m is None:
        raise HTTPException(404, "Mission not found")
    if m.source_kind != "public-report":
        raise HTTPException(400, "Only public-report missions accept manual pins")
    extras = _extras(m)
    if extras.get("aoi_source") != "unknown":
        raise HTTPException(409, f"Mission already has an AOI ({extras.get('aoi_source')})")

    corners = AoiCorners.model_validate(synthesize_aoi(body.lat, body.lon, size_m=400.0))
    m.aoi_corners_json = corners.model_dump_json()
    _set_extras(
        m,
        aoi_source="operator-pin",
        gps_point=[body.lat, body.lon],
        status="processing",
        pinned_by=body.operator_id,
    )

    log_event(
        db, AuditEventType.PUBLIC_REPORT_PINNED,
        mission_id=m.id,
        operator_id=body.operator_id,
        payload={"lat": body.lat, "lon": body.lon, "operator_id": body.operator_id},
    )
    db.commit()
    db.refresh(m)

    background.add_task(process_mission, m.id)
    return MissionOut.model_validate(m)


@router.get("/triage", response_model=list[TriageRowOut])
def triage(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[TriageRowOut]:
    """Public-report missions still awaiting an operator pin. Sorted
    newest-first so the operator works the freshest tip."""
    stmt = (
        select(Mission)
        .where(
            Mission.source_kind == "public-report",
            Mission.deleted_at.is_(None),
        )
        .order_by(Mission.created_at.desc())
        .limit(limit * 2)  # over-fetch; we'll filter by extras_json below
    )
    out: list[TriageRowOut] = []
    for m in db.execute(stmt).scalars().all():
        ex = _extras(m)
        if ex.get("aoi_source") != "unknown":
            continue
        out.append(TriageRowOut(
            mission_id=m.id,
            name=m.name,
            reporter_id=m.reporter_id,
            source_path=str(m.source_path),
            created_at=m.created_at.isoformat() if m.created_at else "",
            caption=ex.get("caption"),
        ))
        if len(out) >= limit:
            break
    return out


@router.get("/recent", response_model=list[RecentRowOut])
def recent(
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[RecentRowOut]:
    """Last N public-report missions across all statuses."""
    stmt = (
        select(Mission)
        .where(
            Mission.source_kind == "public-report",
            Mission.deleted_at.is_(None),
        )
        .order_by(Mission.created_at.desc())
        .limit(limit)
    )
    out: list[RecentRowOut] = []
    for m in db.execute(stmt).scalars().all():
        ex = _extras(m)
        aoi_source = ex.get("aoi_source")
        # Heuristic status:
        #   awaiting_pin  → operator hasn't pinned yet
        #   processing    → just pinned, pipeline scheduled
        #   pinned        → AOI set + has detections (we don't query detections
        #                   here for cheapness; treat "processing" as transient)
        status = ex.get("status") or (
            "awaiting" if aoi_source == "unknown" else "complete"
        )
        out.append(RecentRowOut(
            mission_id=m.id,
            name=m.name,
            reporter_id=m.reporter_id,
            aoi_source=aoi_source,
            status=status,
            created_at=m.created_at.isoformat() if m.created_at else "",
        ))
    return out


@router.get("/thumbnail/{mission_id}")
def thumbnail(mission_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the original public-submission image so the triage UI can
    render a thumbnail without a separate static-file route."""
    m = db.get(Mission, mission_id)
    if m is None or m.source_kind != "public-report":
        raise HTTPException(404, "Public-report mission not found")
    p = Path(m.source_path)
    if not p.exists():
        raise HTTPException(404, "Source file missing on disk")
    return FileResponse(str(p), media_type="image/jpeg")
