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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Alert, AuditEvent, ChatMessage, Detection, MeshWitness, Mission,
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
