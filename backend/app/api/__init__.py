from fastapi import APIRouter

from app.api import alerts, audit, detections, explain, ingest, predict, reports, stream, ws

router = APIRouter(prefix="/api/v1")
router.include_router(ingest.router)
router.include_router(stream.router)
router.include_router(detections.router)
router.include_router(detections.tracks_router)
router.include_router(alerts.router)
router.include_router(audit.router)
router.include_router(predict.router)
router.include_router(explain.router)
router.include_router(reports.router)

# Websocket router is mounted separately (no /api/v1 prefix).
ws_router = ws.router
