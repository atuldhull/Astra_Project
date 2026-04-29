from fastapi import APIRouter

from app.api import adversarial, alerts, anchor, audit, auth, benchmarks, chat, detections, diff, errors, explain, federated, health, ingest, mesh, ood, predict, provenance, public, reports, sentinel, stream, ws

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
router.include_router(adversarial.router)
router.include_router(federated.router)
router.include_router(diff.router)
router.include_router(auth.router)
router.include_router(chat.router)
router.include_router(benchmarks.router)
router.include_router(errors.router)
router.include_router(provenance.router)
router.include_router(anchor.router)
router.include_router(ood.router)
router.include_router(sentinel.router)
router.include_router(mesh.router)
router.include_router(public.router)
router.include_router(health.router)

# Websocket router is mounted separately (no /api/v1 prefix).
ws_router = ws.router

# v3.0/D4.6 — Prometheus /metrics is also mounted top-level (no /api/v1
# prefix) so a generic scraper can hit the conventional path.
metrics_router = health._metrics_router
