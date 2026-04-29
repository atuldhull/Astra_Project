"""
/ood — OOD calibration metadata + reload endpoint.

GET  /ood/calibration  → backend selected, per-class thresholds, sample
                         counts. Drives the Adversarial / Mission-page
                         "method · n samples" tooltip.
POST /ood/reload       → drop the in-memory cache (after re-running
                         scripts/calibrate_ood.py without restarting backend).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.inference import ood_calib
from app.inference.ood_gate import OOD_BACKEND, OOD_THRESHOLD

router = APIRouter(prefix="/ood", tags=["ood"])


@router.get("/calibration")
def calibration() -> dict:
    s = ood_calib.status()
    return {
        "backend": OOD_BACKEND,
        "heuristic_threshold": OOD_THRESHOLD,
        **s,
    }


@router.post("/reload")
def reload_calibration() -> dict:
    ood_calib.clear_cache()
    return {"ok": True, **ood_calib.status()}
