"""
Thin wrapper around Ultralytics YOLO. Lazy-loaded so the backend can boot
even before the trained weights exist (useful during Day 1-2 of the build).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.config import settings

_model = None
_model_lock = Lock()


CLASS_NAMES = [
    "small-vehicle",
    "large-vehicle",
    "aircraft-fixed-wing",
    "aircraft-rotor",
    "ship",
    "storage-depot",
    "harbor",
    "bridge",
]


@dataclass(frozen=True)
class DetectionRecord:
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from ultralytics import YOLO

        path = settings.model_path
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Model weights not found at {path}. "
                "Train first: python training/train.py --config training/configs/astra-v1.yaml"
            )
        _model = YOLO(str(path))
    return _model


def is_ready() -> bool:
    return Path(settings.model_path).exists()


def detect(image_bgr, imgsz: int | None = None, conf: float | None = None) -> list[DetectionRecord]:
    """Run detection on a single BGR image (numpy ndarray H×W×3).
    Returns an empty list if the model isn't loaded yet and is_ready() is False —
    callers can probe is_ready() first to distinguish 'no detections' from 'no model'.
    """
    if not is_ready():
        return []
    model = _load_model()
    results = model.predict(
        image_bgr,
        imgsz=imgsz or settings.imgsz,
        conf=conf if conf is not None else settings.conf_threshold,
        iou=settings.iou_threshold,
        device=settings.inference_device,
        verbose=False,
    )
    out: list[DetectionRecord] = []
    if not results:
        return out
    r = results[0]
    if r.boxes is None:
        return out
    xyxy = r.boxes.xyxy.cpu().numpy()
    conf_arr = r.boxes.conf.cpu().numpy()
    cls_arr = r.boxes.cls.cpu().numpy().astype(int)
    for (x1, y1, x2, y2), c, k in zip(xyxy, conf_arr, cls_arr, strict=True):
        name = CLASS_NAMES[k] if 0 <= k < len(CLASS_NAMES) else str(k)
        out.append(DetectionRecord(int(k), name, float(c), float(x1), float(y1), float(x2), float(y2)))
    return out
