"""
Stage-2 fine-grained airframe classifier — a YOLOv11n-cls model trained on
MAR20 (20 military aircraft variants, e.g. F-22, Su-35, B-52, KC-135).

The cascade flow:
    stage 1 (detector.py)   : YOLOv11n on DOTA → "aircraft-fixed-wing" box
    stage 2 (this module)   : crop the box → YOLOv11n-cls on MAR20 → "F-22 0.84"

Lazy load so the backend boots even before the MAR20 model exists. While the
classifier weights are missing, classify_crop() returns None and the pipeline
falls through to the generic stage-1 label — i.e. the cascade silently
degrades. This is on purpose: Day 1 of Round 2 ships the wiring before the
model is trained.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np

from app.config import RUNS_DIR, WEIGHTS_DIR, settings


_model = None
_model_lock = Lock()
# class-index → airframe name. Populated when the model loads (Ultralytics
# stores names on model.names). Empty until the model is available.
_class_names: list[str] = []


@dataclass(frozen=True)
class AirframeResult:
    """One stage-2 prediction for an aircraft crop."""
    airframe: str
    confidence: float
    top3: list[tuple[str, float]]  # (name, conf) descending


def _weights_path() -> Path:
    """Where we expect the trained MAR20 classifier weights to live.

    Both locations sit under ASTRA_DATA_DIR (see app.config). Day 1 trains into
    the runs/ folder and we copy/symlink the best checkpoint into weights/ once
    the run finishes.
    """
    explicit = WEIGHTS_DIR / "astra-aircraft-v1.pt"
    if explicit.exists():
        return explicit
    # Fallback: training run's best.pt (path produced by Ultralytics)
    return RUNS_DIR / "astra-aircraft-v1" / "weights" / "best.pt"


def is_ready() -> bool:
    """True iff the MAR20 classifier weights are on disk."""
    return _weights_path().exists()


def _load_model():
    global _model, _class_names
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from ultralytics import YOLO

        path = _weights_path()
        if not path.exists():
            raise FileNotFoundError(
                f"MAR20 classifier weights not found at {path}. "
                "Train first: python training/train.py "
                "--config training/configs/astra-aircraft-v1.yaml"
            )
        _model = YOLO(str(path))
        # Ultralytics stores names as a dict {idx: name}; flatten to a list
        names = getattr(_model, "names", None) or {}
        if isinstance(names, dict):
            _class_names = [names[k] for k in sorted(names.keys())]
        else:
            _class_names = list(names)
    return _model


def _crop_from_box(image_bgr: np.ndarray, x1: float, y1: float, x2: float, y2: float, pad_frac: float = 0.10) -> np.ndarray | None:
    """Crop the (x1,y1,x2,y2) AABB from image_bgr with `pad_frac` padding,
    clipped to image bounds. Returns None for degenerate/empty crops."""
    h, w = image_bgr.shape[:2]
    bw = x2 - x1
    bh = y2 - y1
    if bw <= 0 or bh <= 0:
        return None
    px = bw * pad_frac
    py = bh * pad_frac
    cx0 = max(0, int(round(x1 - px)))
    cy0 = max(0, int(round(y1 - py)))
    cx1 = min(w, int(round(x2 + px)))
    cy1 = min(h, int(round(y2 + py)))
    if cx1 - cx0 < 8 or cy1 - cy0 < 8:
        return None
    return image_bgr[cy0:cy1, cx0:cx1]


def classify_crop(
    image_bgr: np.ndarray,
    x1: float, y1: float, x2: float, y2: float,
    pad_frac: float = 0.10,
    topk: int = 3,
) -> AirframeResult | None:
    """Run the MAR20 classifier on a single bbox crop.

    Returns None if the classifier weights aren't on disk yet, or the crop
    is degenerate. Callers should fall through to the stage-1 label in that
    case — the pipeline must remain functional even before MAR20 is trained.
    """
    if not is_ready():
        return None
    crop = _crop_from_box(image_bgr, x1, y1, x2, y2, pad_frac)
    if crop is None:
        return None

    model = _load_model()
    results = model.predict(
        crop,
        device=settings.inference_device,
        imgsz=224,
        verbose=False,
    )
    if not results:
        return None
    r = results[0]
    if r.probs is None:
        return None

    probs = r.probs.data.cpu().numpy()  # shape (n_classes,)
    if probs.size == 0 or not _class_names:
        return None

    order = np.argsort(probs)[::-1]
    top_idx = int(order[0])
    top_name = _class_names[top_idx] if top_idx < len(_class_names) else str(top_idx)
    top_conf = float(probs[top_idx])

    topk = min(topk, len(_class_names))
    top_list: list[tuple[str, float]] = []
    for i in order[:topk]:
        i = int(i)
        nm = _class_names[i] if i < len(_class_names) else str(i)
        top_list.append((nm, float(probs[i])))

    return AirframeResult(airframe=top_name, confidence=top_conf, top3=top_list)


# Class names from stage 1 (detector.CLASS_NAMES) for which we want to
# invoke the cascade. The DOTA detector emits "aircraft-fixed-wing" for
# planes; MAR20 has no rotor variants, so we skip rotors.
CASCADE_TRIGGER_CLASSES = {"aircraft-fixed-wing"}


def should_cascade(class_name: str) -> bool:
    """Whether to run the MAR20 classifier on a stage-1 detection of this class."""
    return class_name in CASCADE_TRIGGER_CLASSES
