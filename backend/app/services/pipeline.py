"""
Inference pipeline service.

process_mission(mission_id) is the single entry point for "an ingested file
becomes detections + alerts + audit events in the database". Called as a
FastAPI BackgroundTask after POST /api/v1/ingest so the client gets a fast
202 response while the work happens asynchronously in-process.

Pipeline stages:
    1. Load Mission from DB (by id)
    2. Decode the uploaded image (or extract N frames from a video)
    3. For each frame: run YOLO detection
    4. For each detection:
        a. Compute pixel-space bbox → Detection row
        b. If AOI corners present: compute lat/lon via bilinear georef
        c. Compute threat score using nearest friendly asset → Alert row
    5. Write INGEST_COMPLETED audit event
    6. Broadcast WebSocket event (future live push)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.api.ws import pool as ws_pool
from app.config import settings
from app.db.models import Alert, AuditEventType, Detection, Mission
from app.db.session import SessionLocal
from app.fusion.georef import AoiCorners, haversine_km, pixel_to_latlon
from app.fusion.narrator import NarratorContext, narrate
from app.fusion.scoring import ScoreInputs, compute_threat_score
from app.inference import aircraft_classifier, detector, ood_gate
from app.services.audit import log_event
from app.services import notifier

log = logging.getLogger("astra.pipeline")

VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MAX_VIDEO_FRAMES = 30  # sample up to N evenly-spaced frames from a clip
FRAME_STRIDE_MS = 33   # placeholder timestamp spacing (~30 FPS)


def _extract_frames(path: Path, max_frames: int = MAX_VIDEO_FRAMES) -> list[tuple[int, int, np.ndarray]]:
    """Return list of (frame_index, timestamp_ms, bgr_image)."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if total <= 0:
        cap.release()
        return []
    # Evenly-spaced indices, capped at max_frames.
    step = max(1, total // max_frames)
    out: list[tuple[int, int, np.ndarray]] = []
    idx = 0
    while idx < total and len(out) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok and frame is not None:
            ts_ms = int(round(idx / fps * 1000))
            out.append((idx, ts_ms, frame))
        idx += step
    cap.release()
    return out


def _aoi_from_mission(mission: Mission) -> AoiCorners | None:
    if not mission.aoi_corners_json:
        return None
    try:
        raw = json.loads(mission.aoi_corners_json)
        return AoiCorners(
            top_left=tuple(raw["top_left"]),
            top_right=tuple(raw["top_right"]),
            bottom_right=tuple(raw["bottom_right"]),
            bottom_left=tuple(raw["bottom_left"]),
        )
    except Exception as exc:
        log.warning("bad aoi_corners_json on mission %d: %s", mission.id, exc)
        return None


def _broadcast_detection(
    mission_id: int,
    det_id: int,
    alert_id: int,
    class_name: str,
    confidence: float,
    lat: float | None,
    lon: float | None,
    threat_score: float,
    track_id: int | None,
    frame_index: int,
    extras: dict,
) -> None:
    """Fire-and-forget broadcast onto /ws/live. Pipeline runs in a sync
    BackgroundTask, so we schedule the async send onto the running loop and
    swallow any exception — websockets must never break ingest."""
    payload = {
        "type": "detection",
        "mission_id": mission_id,
        "detection_id": det_id,
        "alert_id": alert_id,
        "class_name": class_name,
        "confidence": round(confidence, 4),
        "threat_score": round(threat_score, 4),
        "lat": lat,
        "lon": lon,
        "track_id": track_id,
        "frame_index": frame_index,
        "extras": extras or None,
    }
    try:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_pool.broadcast(payload))
        except RuntimeError:
            # No running loop (e.g. invoked from a sync test) — best-effort run
            asyncio.run(ws_pool.broadcast(payload))
    except Exception as exc:
        log.debug("ws broadcast skipped: %s", exc)


def _nearest_friendly(lat: float, lon: float) -> tuple[str | None, float | None]:
    """Return (name, distance_km) of the nearest friendly asset, or (None, None)
    if no assets configured."""
    assets = settings.friendly_assets
    if not assets:
        return None, None
    best_name, best_km = None, float("inf")
    for name, alat, alon in assets:
        d = haversine_km((lat, lon), (alat, alon))
        if d < best_km:
            best_km, best_name = d, name
    return best_name, best_km


def process_mission(mission_id: int) -> dict:
    """Run the full pipeline for a Mission.

    Safe to call from a BackgroundTask — it manages its own DB session.
    Returns a small summary dict for logging / testing.
    """
    if not detector.is_ready():
        log.error("pipeline.process_mission aborted: model not ready")
        return {"ok": False, "reason": "model_not_ready"}

    db: Session = SessionLocal()
    try:
        mission = db.get(Mission, mission_id)
        if not mission:
            return {"ok": False, "reason": "mission_not_found"}

        src = Path(mission.source_path)
        if not src.exists():
            return {"ok": False, "reason": f"source_missing: {src}"}

        aoi = _aoi_from_mission(mission)

        # Gather frame-level detections.
        # For images: single-frame detect() (no tracker needed).
        # For videos: model.track() — stable track_id across frames via ByteTrack.
        suffix = src.suffix.lower()
        frames_iter: list[tuple[int, int, np.ndarray, list]] = []
        if suffix in IMAGE_SUFFIXES:
            img = cv2.imread(str(src), cv2.IMREAD_COLOR)
            if img is None:
                return {"ok": False, "reason": "image_decode_failed"}
            frames_iter = [(0, 0, img, detector.detect(img))]
        elif suffix in VIDEO_SUFFIXES:
            frames_iter = list(
                detector.detect_and_track_video(str(src), max_frames=MAX_VIDEO_FRAMES)
            )
            if not frames_iter:
                return {"ok": False, "reason": "no_frames_extracted"}
        else:
            return {"ok": False, "reason": f"unsupported_suffix: {suffix}"}

        detection_count = 0
        alert_count = 0

        for frame_idx, ts_ms, img, records in frames_iter:
            h, w = img.shape[:2]

            # Cluster class counts for "density" term in scoring.
            cls_counts: dict[str, int] = {}
            for r in records:
                cls_counts[r.class_name] = cls_counts.get(r.class_name, 0) + 1

            for r in records:
                # Compute geo if AOI provided.
                lat = lon = None
                dist_km = None
                nearest_name = None
                if aoi is not None:
                    cx = (r.x1 + r.x2) / 2
                    cy = (r.y1 + r.y2) / 2
                    lat, lon = pixel_to_latlon(cx, cy, w, h, aoi)
                    nearest_name, dist_km = _nearest_friendly(lat, lon)

                # Stage-2 cascade: if this detection is an aircraft AND the
                # MAR20 classifier weights are available, get the airframe ID.
                # Failures here are non-fatal — the generic stage-1 label still
                # appears, the cascade is best-effort.
                extras: dict = {}
                if aircraft_classifier.should_cascade(r.class_name) and aircraft_classifier.is_ready():
                    try:
                        af = aircraft_classifier.classify_crop(img, r.x1, r.y1, r.x2, r.y2)
                        if af is not None:
                            extras["airframe"] = af.airframe
                            extras["airframe_confidence"] = round(af.confidence, 4)
                            extras["airframe_top3"] = [
                                {"name": n, "conf": round(c, 4)} for n, c in af.top3
                            ]
                    except Exception as exc:
                        log.warning("aircraft cascade failed for det in mission %d: %s", mission.id, exc)

                # OOD gatekeeper: confidence + aspect + edge-density heuristics.
                # If flagged, the frontend renders this detection greyed-out
                # with a "?" badge — the system shows it knew it didn't know.
                try:
                    ood = ood_gate.assess_detection(
                        img, r.class_name, r.confidence, r.x1, r.y1, r.x2, r.y2,
                    )
                    extras["ood_score"] = ood.score
                    extras["ood_flag"] = ood.flagged
                    if ood.reasons:
                        extras["ood_reasons"] = ood.reasons
                except Exception as exc:
                    log.warning("ood gate failed for det in mission %d: %s", mission.id, exc)

                det = Detection(
                    mission_id=mission.id,
                    frame_index=frame_idx,
                    frame_timestamp_ms=ts_ms,
                    class_id=r.class_id,
                    class_name=r.class_name,
                    confidence=r.confidence,
                    x1=r.x1, y1=r.y1, x2=r.x2, y2=r.y2,
                    lat=lat, lon=lon,
                    track_id=r.track_id,
                    extras_json=json.dumps(extras) if extras else None,
                )
                db.add(det)
                db.flush()
                detection_count += 1

                score = compute_threat_score(
                    ScoreInputs(
                        class_name=r.class_name,
                        confidence=r.confidence,
                        distance_km=dist_km,
                        movement_toward_asset=0.0,  # no tracker yet
                        same_class_count_in_aoi=cls_counts.get(r.class_name, 1),
                    )
                )

                breakdown = {
                    "class_term": round(score.class_term, 4),
                    "proximity_term": round(score.proximity_term, 4),
                    "motion_term": round(score.motion_term, 4),
                    "count_term": round(score.count_term, 4),
                    "confidence_term": round(score.confidence_term, 4),
                    "distance_km": round(dist_km, 3) if dist_km is not None else None,
                    "nearest_asset": nearest_name,
                }

                narrative_text = narrate(
                    NarratorContext(
                        class_name=r.class_name,
                        confidence=r.confidence,
                        threat_score=score.score,
                        distance_km=dist_km,
                        nearest_asset=nearest_name,
                        same_class_count=cls_counts.get(r.class_name, 1),
                    )
                )

                alert = Alert(
                    mission_id=mission.id,
                    detection_id=det.id,
                    threat_score=score.score,
                    score_breakdown_json=json.dumps(breakdown),
                    narrative=narrative_text,
                )
                db.add(alert)
                db.flush()
                alert_count += 1

                # Live push: notify any /ws/live subscribers (e.g. the Map page)
                # that a new detection landed. Best-effort — never block or
                # crash the pipeline if the websocket fan-out fails.
                _broadcast_detection(
                    mission_id=mission.id,
                    det_id=det.id,
                    alert_id=alert.id,
                    class_name=r.class_name,
                    confidence=r.confidence,
                    lat=lat, lon=lon,
                    threat_score=score.score,
                    track_id=r.track_id,
                    frame_index=frame_idx,
                    extras=extras,
                )

                # Telegram fan-out for high-threat detections. Only fires if
                # TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars are set AND
                # the score crosses TELEGRAM_ALERT_THRESHOLD. No-op otherwise.
                if notifier.is_configured() and score.score >= notifier.threshold():
                    try:
                        msg = notifier.format_alert_text(
                            mission_name=mission.name,
                            class_name=r.class_name,
                            threat_score=score.score,
                            narrative=narrative_text,
                            nearest_asset=nearest_name,
                            distance_km=dist_km,
                            airframe=extras.get("airframe"),
                        )
                        notifier.send_alert(msg, threat_score=score.score)
                    except Exception as exc:
                        log.debug("telegram notify skipped: %s", exc)

        # Track count for audit payload (videos have multiple unique track_ids)
        track_ids_seen = {r.track_id for _, _, _, recs in frames_iter for r in recs if r.track_id is not None}
        frame_count = len(frames_iter)

        log_event(
            db,
            AuditEventType.INGEST_COMPLETED,
            mission_id=mission.id,
            payload={
                "detection_count": detection_count,
                "alert_count": alert_count,
                "frame_count": frame_count,
                "track_count": len(track_ids_seen),
                "aoi_present": aoi is not None,
            },
        )
        db.commit()

        log.info(
            "pipeline ok: mission=%d frames=%d detections=%d tracks=%d alerts=%d aoi=%s",
            mission.id, frame_count, detection_count, len(track_ids_seen), alert_count, aoi is not None,
        )
        return {
            "ok": True,
            "mission_id": mission.id,
            "frames": frame_count,
            "detections": detection_count,
            "tracks": len(track_ids_seen),
            "alerts": alert_count,
        }

    except Exception as exc:
        db.rollback()
        log.exception("pipeline failed for mission %d: %s", mission_id, exc)
        return {"ok": False, "reason": f"exception: {exc}"}
    finally:
        db.close()
