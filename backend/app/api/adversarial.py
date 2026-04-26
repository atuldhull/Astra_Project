"""
Adversarial robustness endpoint.

POST /api/v1/adversarial
  multipart: file, epsilon (0..0.2), method ("fgsm" | "noise")
Returns JSON:
  {
    "original": {"detection_count": N, "class_counts": {...}, "detections": [...]},
    "perturbed": {"detection_count": M, "class_counts": {...}, "detections": [...]},
    "perturbed_image_base64": "data:image/jpeg;base64,..." (for display),
    "epsilon": 0.03,
    "method_used": "fgsm",
    "latency_ms": 123.4
  }
"""

from __future__ import annotations

import base64
import time

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.inference import detector
from app.inference.adversarial import perturb

router = APIRouter(prefix="/adversarial", tags=["adversarial"])


class DetectionBrief(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionsSummary(BaseModel):
    detection_count: int
    class_counts: dict[str, int]
    detections: list[DetectionBrief]


class AdversarialResponse(BaseModel):
    epsilon: float
    method_used: str
    latency_ms: float
    image_size: dict
    model_variant: str
    original: DetectionsSummary
    perturbed: DetectionsSummary
    perturbed_image_base64: str
    # Round-2: retention metric for the A/B narrative.
    # retention = perturbed_count / max(original_count, 1)
    retention: float


def _summarize(records) -> DetectionsSummary:
    cls_counts: dict[str, int] = {}
    out_dets: list[DetectionBrief] = []
    for r in records:
        cls_counts[r.class_name] = cls_counts.get(r.class_name, 0) + 1
        out_dets.append(DetectionBrief(
            class_id=r.class_id,
            class_name=r.class_name,
            confidence=r.confidence,
            x1=r.x1, y1=r.y1, x2=r.x2, y2=r.y2,
        ))
    return DetectionsSummary(
        detection_count=len(records),
        class_counts=cls_counts,
        detections=out_dets,
    )


@router.get("/variants")
def list_variants() -> dict:
    """Which model variants are on disk. Frontend's A/B picker greys out
    missing ones (e.g. v1-hardened before adv-training has run)."""
    return {"variants": detector.available_variants()}


@router.post("", response_model=AdversarialResponse)
async def run_adversarial(
    file: UploadFile = File(...),
    epsilon: float = Form(0.03, ge=0.0, le=0.5),
    method: str = Form("fgsm"),
    model_variant: str = Form("v1"),
) -> AdversarialResponse:
    if method not in ("fgsm", "noise"):
        raise HTTPException(400, "method must be 'fgsm' or 'noise'")
    if model_variant not in {"v1", "v1-hardened"}:
        raise HTTPException(400, f"Unknown model_variant: {model_variant}")
    if not detector.is_ready(model_variant):
        raise HTTPException(503, f"Model variant {model_variant!r} not loaded — weights not on disk")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload")
    img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Could not decode image")
    h, w = img.shape[:2]

    t0 = time.perf_counter()

    # Lazy-load the chosen variant. Reused by both detect() calls below
    # AND by the perturb() FGSM gradient pass.
    from app.inference.detector import _load_model
    model = _load_model(model_variant)

    # Detect on original
    original_records = detector.detect(img, variant=model_variant)

    # Perturb (FGSM uses the same model's gradient — perturbation is
    # variant-specific by design).
    perturbed_img, method_used = perturb(model, img, epsilon, method=method)

    # Detect on perturbed
    perturbed_records = detector.detect(perturbed_img, variant=model_variant)

    latency_ms = (time.perf_counter() - t0) * 1000

    # Encode perturbed image as base64 JPEG (smaller than PNG)
    ok, buf = cv2.imencode(".jpg", perturbed_img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise HTTPException(500, "failed to encode perturbed image")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")

    orig_count = len(original_records)
    pert_count = len(perturbed_records)
    retention = (pert_count / orig_count) if orig_count > 0 else 1.0

    return AdversarialResponse(
        epsilon=float(epsilon),
        method_used=method_used,
        latency_ms=round(latency_ms, 2),
        image_size={"width": int(w), "height": int(h)},
        model_variant=model_variant,
        original=_summarize(original_records),
        perturbed=_summarize(perturbed_records),
        perturbed_image_base64=f"data:image/jpeg;base64,{b64}",
        retention=round(retention, 4),
    )
