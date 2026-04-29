"""
/health/dashboard (D3.6) — single aggregated readout for the operator's
Health page.

This rolls up every "is the system actually working?" signal that's
otherwise scattered across half a dozen endpoints (provenance, anchor,
ood, benchmarks, errors, db) into one read so the Health page is a
single fetch + 10-second poll.

Auth: requires JWT (any role). When ASTRA_AUTH_ENABLED=0 the auth_required
dep returns a synthetic admin operator, so demos still work.
"""

from __future__ import annotations

import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Alert, AlertStatus, AuditEvent, ChatMessage, Detection, MeshWitness, Mission,
)
from app.db.session import get_db
from app.inference import detector, ood_calib
from app.services.anchor import last_anchor, count_anchors
from app.services.auth import Operator, auth_required
from app.services.provenance import model_hash

router = APIRouter(prefix="/health", tags=["health"])

REPO_ROOT = Path(__file__).resolve().parents[3]
ERROR_LOG = REPO_ROOT / ".frontend-errors.log"
LATENCY_PATH = REPO_ROOT / "benchmarks" / "latency.json"
DETECTOR_VAL_PATH = REPO_ROOT / "benchmarks" / "detector_val.json"

_BOOT_TS = time.time()


def _read_json_safely(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _backend_block() -> dict:
    return {
        "uptime_s": round(time.time() - _BOOT_TS, 1),
        "version": "3.0.0-rc3",
        "device": settings.inference_device,
        "model_path": str(settings.model_path),
        "cuda_available": _cuda_available(),
        "python": platform.python_version(),
        "platform": platform.system(),
    }


def _cuda_available() -> bool:
    try:
        import torch  # noqa: WPS433
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _models_block() -> dict:
    try:
        from app.inference import aircraft_classifier as cascade
        cascade_ready = bool(cascade.is_ready())
    except Exception:
        cascade_ready = False
    try:
        from app.services.rag import _llm_available, PHI_PATH
        llm_ready = bool(_llm_available())
        llm_path = str(PHI_PATH)
    except Exception:
        llm_ready = False
        llm_path = ""
    try:
        mh = model_hash()
    except Exception:
        mh = "unavailable"
    return {
        "detector_ready": bool(detector.is_ready()),
        "cascade_ready": cascade_ready,
        "llm_ready": llm_ready,
        "model_hash": mh,
        "llm_path": llm_path,
    }


def _db_block(db: Session) -> dict:
    def _count(stmt) -> int:
        try:
            return int(db.execute(stmt).scalar_one() or 0)
        except Exception:
            return 0

    return {
        "mission_count": _count(
            select(func.count()).select_from(Mission).where(Mission.deleted_at.is_(None))
        ),
        "deleted_mission_count": _count(
            select(func.count()).select_from(Mission).where(Mission.deleted_at.is_not(None))
        ),
        "detection_count": _count(select(func.count()).select_from(Detection)),
        "alert_count": _count(select(func.count()).select_from(Alert)),
        "audit_count": _count(select(func.count()).select_from(AuditEvent)),
        "chat_message_count": _count(select(func.count()).select_from(ChatMessage)),
        "peer_witness_count": _count(select(func.count()).select_from(MeshWitness)),
    }


def _chain_block(db: Session) -> dict:
    tip_row = db.execute(
        select(AuditEvent.id, AuditEvent.row_hash)
        .order_by(AuditEvent.id.desc()).limit(1)
    ).first()
    tip_id = int(tip_row[0]) if tip_row else None
    tip = tip_row[1] if tip_row else None
    last = last_anchor()
    return {
        "tip": tip,
        "tip_id": tip_id,
        "last_anchor": last.to_dict() if last else None,
        "anchor_total": count_anchors(),
    }


def _ood_block() -> dict:
    try:
        return ood_calib.status()
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def _errors_block() -> dict:
    if not ERROR_LOG.exists():
        return {"count_24h": 0, "last_message": None, "last_ts": None}
    horizon = time.time() - 86_400
    count_24h = 0
    last_message: str | None = None
    last_ts: str | None = None
    try:
        # Tail last ~200 lines; cheap and bounded.
        with ERROR_LOG.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-200:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            ts = rec.get("received_at") or rec.get("ts")
            try:
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
            except Exception:
                ts_dt = None
            if ts_dt is not None and ts_dt.timestamp() >= horizon:
                count_24h += 1
            last_message = rec.get("message") or last_message
            last_ts = ts or last_ts
    except Exception:
        pass
    return {"count_24h": count_24h, "last_message": last_message, "last_ts": last_ts}


def _file_age_block(path: Path) -> dict | None:
    data = _read_json_safely(path)
    if not data:
        return None
    captured_at = data.get("captured_at")
    return {
        "captured_at": captured_at,
        "data": data,
        "path": str(path),
    }


@router.get("/dashboard")
def dashboard(
    op: Operator = Depends(auth_required),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregated readout consumed by /health (the page).

    Single round-trip on a 10s poll. Each block is independently fault-
    tolerant; one missing weight file or stale benchmark JSON cannot
    take the whole readout down.
    """
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "operator": {"id": op.id, "role": op.role},
        "backend": _backend_block(),
        "models": _models_block(),
        "db": _db_block(db),
        "chain": _chain_block(db),
        "ood": _ood_block(),
        "errors": _errors_block(),
        "latency": _file_age_block(LATENCY_PATH),
        "map": _file_age_block(DETECTOR_VAL_PATH),
    }


# ── D4.6 — Prometheus text-format metrics ────────────────────────────

# Registered as a sibling at /metrics (no /health prefix) so a generic
# Prometheus scraper can hit the conventional path. We re-export this
# router from app.api.__init__ as a separate include without prefix.
_metrics_router = APIRouter(tags=["metrics"])


def _ptype(name: str, kind: str, help_text: str) -> str:
    return f"# HELP {name} {help_text}\n# TYPE {name} {kind}\n"


@_metrics_router.get("/metrics")
def prometheus_metrics(db: Session = Depends(get_db)) -> Response:
    """Prometheus exposition (text format).

    Reuses the same blocks the Health page consumes — no new aggregation
    logic. Numeric fields only; ISO timestamps + hashes are skipped.
    The endpoint is intentionally NOT auth-gated: scrapers run as their
    own user-agent, and the data exposed is non-sensitive operational
    counters (no operator IDs, no audit row hashes, no detection coords).
    """
    from fastapi.responses import Response as FastResponse

    backend = _backend_block()
    models = _models_block()
    db_block = _db_block(db)
    chain = _chain_block(db)
    ood = _ood_block()
    errors = _errors_block()
    latency = _file_age_block(LATENCY_PATH)
    mapb = _file_age_block(DETECTOR_VAL_PATH)

    lines: list[str] = []

    # Backend
    lines.append(_ptype("astra_uptime_seconds", "gauge", "Uptime in seconds since uvicorn boot."))
    lines.append(f"astra_uptime_seconds {backend['uptime_s']}\n")
    lines.append(_ptype("astra_cuda_available", "gauge", "1 if torch.cuda.is_available()."))
    lines.append(f"astra_cuda_available {1 if backend['cuda_available'] else 0}\n")

    # Models
    lines.append(_ptype("astra_model_ready", "gauge", "Per-model readiness (1=loaded, 0=absent)."))
    lines.append(f'astra_model_ready{{model="detector"}} {1 if models["detector_ready"] else 0}\n')
    lines.append(f'astra_model_ready{{model="cascade"}}  {1 if models["cascade_ready"] else 0}\n')
    lines.append(f'astra_model_ready{{model="llm"}}      {1 if models["llm_ready"] else 0}\n')

    # DB rows
    lines.append(_ptype("astra_db_rows", "gauge", "Row counts per table."))
    for table in ("mission_count", "deleted_mission_count", "detection_count",
                  "alert_count", "audit_count", "chat_message_count",
                  "peer_witness_count"):
        label = table.replace("_count", "")
        lines.append(f'astra_db_rows{{table="{label}"}} {db_block[table]}\n')

    # Chain
    lines.append(_ptype("astra_audit_tip_id", "gauge", "Latest audit row id (chain tip)."))
    lines.append(f"astra_audit_tip_id {chain['tip_id'] or 0}\n")
    lines.append(_ptype("astra_anchor_total", "gauge", "Number of anchor entries in the local-file backend."))
    lines.append(f"astra_anchor_total {chain['anchor_total']}\n")

    # OOD
    lines.append(_ptype("astra_ood_available", "gauge", "1 if a Mahalanobis OOD calibration is loaded."))
    lines.append(f"astra_ood_available {1 if ood.get('available') else 0}\n")

    # Errors
    lines.append(_ptype("astra_frontend_errors_24h", "gauge", "Frontend ErrorBoundary reports in the last 24h."))
    lines.append(f"astra_frontend_errors_24h {errors['count_24h']}\n")

    # Latency
    if latency and latency.get("data"):
        d = latency["data"]
        lines.append(_ptype("astra_ingest_latency_ms", "gauge", "Ingest→alert pipeline latency from the last capture."))
        for q in ("p50_ms", "p95_ms", "p99_ms", "mean_ms"):
            v = d.get(q)
            if isinstance(v, (int, float)):
                lines.append(f'astra_ingest_latency_ms{{quantile="{q[:-3]}"}} {v}\n')

    # mAP
    if mapb and mapb.get("data"):
        d = mapb["data"]
        lines.append(_ptype("astra_detector_map", "gauge", "Detector mAP from the last capture."))
        for k, key in (("0.5", "map_50"), ("0.5_0.95", "map_50_95")):
            v = d.get(key)
            if isinstance(v, (int, float)):
                lines.append(f'astra_detector_map{{iou="{k}"}} {v}\n')
        for k in ("precision", "recall"):
            v = d.get(k)
            if isinstance(v, (int, float)):
                lines.append(_ptype(f"astra_detector_{k}", "gauge", f"Detector {k} from the last capture."))
                lines.append(f"astra_detector_{k} {v}\n")

    # D5.5 — alerts by status (operationally interesting; built fresh each
    # scrape so cancellation / status churn surfaces immediately).
    try:
        rows = db.execute(select(Alert.status, func.count()).group_by(Alert.status)).all()
        if rows:
            lines.append(_ptype(
                "astra_alerts_by_status",
                "gauge",
                "Alert counts per status (pending, confirmed, rejected, escalated, engaged).",
            ))
            # Initialize zeros for every known status so a Grafana panel
            # gets stable series even before any alert lands in that bucket.
            counts: dict[str, int] = {s.value: 0 for s in AlertStatus}
            for status, c in rows:
                key = status.value if hasattr(status, "value") else str(status)
                counts[key] = int(c or 0)
            for k, v in counts.items():
                lines.append(f'astra_alerts_by_status{{status="{k}"}} {v}\n')
    except Exception:
        pass

    # D5.5 — request counter + latency histogram from middleware.
    try:
        from app.services.ops_metrics import get_state
        state = get_state()
        snap = list(state.snapshot_text())
        if snap:
            lines.append(_ptype(
                "astra_request_total",
                "counter",
                "HTTP request count by endpoint, method, status.",
            ))
            lines.append(_ptype(
                "astra_request_latency_seconds",
                "histogram",
                "HTTP request latency distribution per endpoint+method.",
            ))
            for line in snap:
                lines.append(line + "\n")
    except Exception:
        pass

    body = "".join(lines)
    return FastResponse(content=body, media_type="text/plain; version=0.0.4")
