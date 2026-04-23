"""
Explainability endpoint — returns a Grad-CAM / EigenCAM heatmap PNG
for a given image + optional detection bbox. Streamed as image/png
so the browser can display it directly as <img src=blob:...>.
"""

from __future__ import annotations

import time

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.inference import detector
from app.inference.gradcam import compute_heatmap_png

router = APIRouter(prefix="/explain", tags=["explain"])


@router.post("", responses={200: {"content": {"image/png": {}}}})
async def explain(
    file: UploadFile = File(...),
    x1: float | None = Form(None),
    y1: float | None = Form(None),
    x2: float | None = Form(None),
    y2: float | None = Form(None),
) -> Response:
    if not detector.is_ready():
        raise HTTPException(503, "Model not loaded")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload")
    img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Could not decode image")

    box = None
    if all(v is not None for v in (x1, y1, x2, y2)):
        box = (float(x1), float(y1), float(x2), float(y2))  # type: ignore[arg-type]

    # Lazy-load the model to reuse the same instance as /predict
    from app.inference.detector import _load_model
    model = _load_model()

    t0 = time.perf_counter()
    png = compute_heatmap_png(model, img, box_xyxy=box)
    latency_ms = (time.perf_counter() - t0) * 1000

    return Response(
        content=png,
        media_type="image/png",
        headers={"X-Latency-Ms": f"{latency_ms:.2f}"},
    )
