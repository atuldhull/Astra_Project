"""
URL-based ingest — accepts an HTTP/HTTPS/RTSP source URL instead of a file
upload. For the demo this means: paste any live-stream URL or remote video
URL and ASTRA processes it like a drone feed.

Implementation: cv2.VideoCapture supports both RTSP and HTTP natively; we
capture up to MAX_FRAMES over MAX_DURATION_S, stitch them into a local MP4
in the uploads dir, then hand the file path to the existing pipeline (which
already knows how to extract frames from a video).

This keeps the downstream pipeline code identical — a URL mission is just
a video mission whose source happens to have been streamed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4

import cv2
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEventType, Mission
from app.db.session import get_db
from app.schemas import AoiCorners, MissionOut
from app.services.audit import log_event
from app.services.pipeline import process_mission

router = APIRouter(prefix="/ingest", tags=["ingest"])

MAX_FRAMES = 60
MAX_DURATION_S = 15
READ_TIMEOUT_S = 8  # give up waiting for the first frame after this long


class UrlIngestRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    url: str = Field(..., description="HTTP, HTTPS, or RTSP URL")
    aoi_corners: AoiCorners | None = None
    max_frames: int = Field(default=30, ge=1, le=MAX_FRAMES)
    duration_s: int = Field(default=5, ge=1, le=MAX_DURATION_S)


def _capture_to_file(url: str, out_path: Path, max_frames: int, duration_s: int) -> tuple[int, int, int]:
    """Capture from a video source URL into a local MP4 file.

    Returns (frames_written, width, height). Raises on failure.
    """
    # Force FFmpeg backend on Windows for RTSP reliability
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise RuntimeError(f"could not open source: {url}")

    # Grab first frame with timeout (many streams need a warmup read)
    t0 = time.time()
    first_frame = None
    while time.time() - t0 < READ_TIMEOUT_S:
        ok, frame = cap.read()
        if ok and frame is not None:
            first_frame = frame
            break
    if first_frame is None:
        cap.release()
        raise RuntimeError(f"no frames received within {READ_TIMEOUT_S}s (check URL / network)")

    h, w = first_frame.shape[:2]
    # Use a reasonable FPS — 15 for most streams is plenty
    fps = 15.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("could not open output writer (codec issue)")

    frames_written = 0
    writer.write(first_frame)
    frames_written += 1

    start = time.time()
    while frames_written < max_frames and (time.time() - start) < duration_s:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        writer.write(frame)
        frames_written += 1

    writer.release()
    cap.release()
    return frames_written, w, h


@router.post("/url", response_model=MissionOut)
async def create_mission_from_url(
    background: BackgroundTasks,
    name: str = Form(..., min_length=1, max_length=128),
    url: str = Form(...),
    aoi_corners: str | None = Form(None),
    max_frames: int = Form(30, ge=1, le=MAX_FRAMES),
    duration_s: int = Form(5, ge=1, le=MAX_DURATION_S),
    db: Session = Depends(get_db),
) -> MissionOut:
    # Basic URL scheme validation
    url_stripped = url.strip()
    if not url_stripped:
        raise HTTPException(400, "url is required")
    scheme_ok = any(url_stripped.lower().startswith(s) for s in ("http://", "https://", "rtsp://", "rtmp://", "file://"))
    if not scheme_ok:
        raise HTTPException(400, "url must use http / https / rtsp / rtmp / file scheme")

    corners_obj: AoiCorners | None = None
    if aoi_corners:
        try:
            corners_obj = AoiCorners.model_validate_json(aoi_corners)
        except Exception as exc:
            raise HTTPException(400, f"Invalid aoi_corners: {exc}") from exc

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.uploads_dir / f"{name}-stream-{uuid4().hex[:8]}.mp4"

    # Capture frames synchronously — we want to know it worked before returning 200
    try:
        frames, w, h = _capture_to_file(url_stripped, dest, max_frames, duration_s)
    except Exception as exc:
        if dest.exists():
            try: dest.unlink()
            except Exception: pass
        raise HTTPException(502, f"stream capture failed: {exc}") from exc

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
            "source": "url",
            "url": url_stripped,
            "frames_captured": frames,
            "width": w,
            "height": h,
            "saved_to": str(dest),
        },
    )
    db.commit()
    db.refresh(mission)

    # Kick off inference pipeline just like the file-upload path
    background.add_task(process_mission, mission.id)
    return MissionOut.model_validate(mission)
