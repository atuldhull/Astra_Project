"""Live inference endpoint.

Accepts an image upload, runs YOLO detection synchronously, returns
detections + image dimensions. Used by the Mission page to draw boxes
over a previewed image without the full ingest/DB pipeline.
"""

from __future__ import annotations

import time

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.inference import detector

router = APIRouter(prefix="/predict", tags=["predict"])


class PredictDetection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class PredictResponse(BaseModel):
    image: dict
    detections: list[PredictDetection]
    latency_ms: float
    model: dict


@router.post("", response_model=PredictResponse)
async def predict(file: UploadFile = File(...)) -> PredictResponse:
    if not detector.is_ready():
        raise HTTPException(503, "Model not loaded — check ASTRA_MODEL_PATH")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty upload")

    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, f"Could not decode image (filename={file.filename})")

    h, w = img.shape[:2]

    t0 = time.perf_counter()
    records = detector.detect(img)
    latency_ms = (time.perf_counter() - t0) * 1000

    return PredictResponse(
        image={"width": int(w), "height": int(h)},
        detections=[
            PredictDetection(
                class_id=r.class_id,
                class_name=r.class_name,
                confidence=r.confidence,
                x1=r.x1, y1=r.y1, x2=r.x2, y2=r.y2,
            )
            for r in records
        ],
        latency_ms=round(latency_ms, 2),
        model={"name": "astra-v1", "backbone": "yolo11n", "imgsz": 640},
    )
