from fastapi import APIRouter

from app.api import alerts, audit, detections, explain, ingest, predict, ws

router = APIRouter(prefix="/api/v1")
router.include_router(ingest.router)
router.include_router(detections.router)
router.include_router(alerts.router)
router.include_router(audit.router)
router.include_router(predict.router)
router.include_router(explain.router)

# Websocket router is mounted separately (no /api/v1 prefix).
ws_router = ws.router
