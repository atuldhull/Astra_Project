"""Diagnostic-grade FastAPI app: skips every router that transitively
imports torch / ultralytics / cv2 inference modules.

CRITICAL: imports each router via its FULL module path (not via
`from app.api import X`), because `app/api/__init__.py` itself imports
all 23 routers eagerly — which would trigger torch via the
inference-heavy ones.

Used when the host is RAM-constrained and a full `app.main` boot would
deadlock on `import torch`. Lets us still verify rc5.1's defining
surfaces:

  * /health                    (lite-version)
  * /metrics                   (top-level, ops middleware active)
  * /api/v1/audit/*            (incl. snapshot, latest-by-alert)
  * /api/v1/anchor/*           (chain anchoring)
  * /api/v1/auth/*             (JWT scaffold)
  * /api/v1/mesh/*             (D3.4 peer witness)
  * /api/v1/errors             (frontend error sink)
  * /api/v1/benchmarks/*       (read-only benchmark JSON)
  * /api/v1/diff/*             (mission diff)
  * /api/v1/detections         (DB read)
  * /api/v1/alerts/*           (DB read + WS broadcast)
  * /api/v1/reports/*          (PDF reports)

Routers DELIBERATELY omitted because they require torch / llama_cpp:
  ingest, predict, explain, adversarial, federated, sentinel, ood,
  health (imports detector), chat (imports rag), public/stream
  (import pipeline), provenance.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import each router via its full module path so app/api/__init__.py
# (which eagerly imports the heavy ones) is NOT loaded.
from app.api.alerts import router as alerts_router
from app.api.anchor import router as anchor_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.benchmarks import router as benchmarks_router
from app.api.detections import router as detections_router
from app.api.detections import tracks_router as detection_tracks_router
from app.api.diff import router as diff_router
from app.api.errors import router as errors_router
from app.api.mesh import router as mesh_router
from app.api.reports import router as reports_router
from app.api.ws import router as ws_module_router

# /metrics router — defined inside app.api.health which imports detector,
# so we re-build a minimal /metrics here that calls the same emission.
from app.services.ops_metrics import metrics_middleware, get_state

app = FastAPI(
    title="ASTRA (lite)",
    description="RAM-constrained diagnostic boot — torch-touching routers omitted",
    version="0.1.0-lite",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(metrics_middleware)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(detections_router)
api_router.include_router(detection_tracks_router)
api_router.include_router(alerts_router)
api_router.include_router(audit_router)
api_router.include_router(reports_router)
api_router.include_router(diff_router)
api_router.include_router(auth_router)
api_router.include_router(benchmarks_router)
api_router.include_router(errors_router)
api_router.include_router(anchor_router)
api_router.include_router(mesh_router)

app.include_router(api_router)
app.include_router(ws_module_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": app.version, "mode": "lite"}


@app.get("/metrics")
def prometheus_metrics() -> "Response":  # type: ignore[name-defined]
    """Lite /metrics — ops middleware counters only (no DB-rollup blocks).
    The full /metrics (with astra_alerts_by_status + astra_db_rows) lives
    in app.api.health which we can't import here. This still exposes the
    request counter + latency histogram which are the SRE-relevant ones."""
    from fastapi.responses import Response
    state = get_state()
    lines = [
        "# HELP astra_request_total HTTP request count by endpoint, method, status.\n",
        "# TYPE astra_request_total counter\n",
        "# HELP astra_request_latency_seconds HTTP request latency distribution.\n",
        "# TYPE astra_request_latency_seconds histogram\n",
    ]
    for line in state.snapshot_text():
        lines.append(line + "\n")
    return Response(content="".join(lines), media_type="text/plain; version=0.0.4")


@app.get("/")
def root() -> dict:
    return {"name": "ASTRA-lite", "docs": "/docs"}
