"""
/provenance — public key, fingerprint, per-detection verify.

GET  /provenance/key                     → status + public key PEM + fingerprint
GET  /provenance/verify/{detection_id}   → re-verify the on-disk signature
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Detection
from app.db.session import get_db
from app.services.provenance import (
    DetectionFields, model_hash, status, verify_detection,
)

router = APIRouter(prefix="/provenance", tags=["provenance"])


@router.get("/key")
def provenance_key() -> dict:
    """Public key + fingerprint for the UI to display in the Audit footer
    and the Detection-verify modal. Public, no auth required."""
    return status()


@router.get("/verify/{detection_id}")
def verify(detection_id: int, db: Session = Depends(get_db)) -> dict:
    """Re-verify the stored Ed25519 signature against the canonical
    payload. Returns ok=true only if the row hasn't been tampered with
    AND the model hash hasn't drifted from the one signing claimed."""
    det = db.get(Detection, detection_id)
    if not det:
        raise HTTPException(404, f"Detection {detection_id} not found")
    if not det.signature_b64:
        return {
            "ok": False, "reason": "unsigned (provenance disabled at ingest time)",
            "detection_id": detection_id,
        }
    if not det.image_sha256:
        return {
            "ok": False, "reason": "missing image_sha256",
            "detection_id": detection_id,
        }
    fields = DetectionFields(
        mission_id=det.mission_id,
        class_id=det.class_id,
        class_name=det.class_name,
        confidence=det.confidence,
        x1=det.x1, y1=det.y1, x2=det.x2, y2=det.y2,
        image_sha256=det.image_sha256,
        model_hash=model_hash(),
        created_at_iso=det.created_at.isoformat() if det.created_at else "",
    )
    result = verify_detection(fields, det.signature_b64)
    return {
        **result,
        "detection_id": detection_id,
        "signed_payload": {
            "mission_id": det.mission_id,
            "class_name": det.class_name,
            "confidence": round(det.confidence, 4),
            "image_sha256_short": det.image_sha256[:16] + "…",
            "model_hash_short": (model_hash() or "")[:16] + "…",
        },
    }
