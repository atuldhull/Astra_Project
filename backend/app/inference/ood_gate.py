"""
Out-of-distribution gatekeeper.

Goal: flag YOLO detections that are likely *not* one of the 8 DOTA classes
the model was trained on. The model has no "unknown" label, so it confidently
mis-labels alien objects (a building roof as a ship, a tennis court as a
storage depot). Without a gate the demo viewer thinks the model is wrong;
with the gate, the same detection shows as grey-with-"?" and the demo viewer
sees that the system *knew* it didn't know.

Three backends behind one interface — selectable via ASTRA_OOD_BACKEND:

  * mahalanobis (T1.3, DEFAULT when calibrated weights exist):
      9-D model-agnostic feature vector → per-class Gaussian → squared
      Mahalanobis distance to class mean → flag if > 99th percentile of
      in-distribution distances. Fit by scripts/calibrate_ood.py.

  * heuristic (R2 baseline, ALWAYS available — fallback):
      OOD score per detection from three signals:
        - low confidence relative to its class's training-time mean
        - extreme aspect ratio for the claimed class (e.g. a 5:1 ship)
        - low edge density inside the bbox

  * SAM (placeholder, not shipped):
      Mask the bbox interior with SAM, count components, compare with
      YOLO's expectation. Hook below; weights+code TBD.

Result is stashed into Detection.extras_json as:
    {"ood_score": 0.62, "ood_flag": true,
     "ood_reasons": ["mahalanobis(d2=12.4 > τ=8.7)"]}
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import cv2
import numpy as np

from app.inference import ood_calib

OOD_BACKEND = os.environ.get("ASTRA_OOD_BACKEND", "mahalanobis").lower()


# Per-class typical aspect ratio range (w/h). Outside this range we suspect
# the model is bending its prediction. Numbers chosen from rough inspection
# of DOTA training tiles — refine empirically if false-positive rate is high.
TYPICAL_ASPECT: dict[str, tuple[float, float]] = {
    "small-vehicle":       (0.4, 2.5),
    "large-vehicle":       (0.4, 3.5),
    "aircraft-fixed-wing": (0.5, 2.5),
    "aircraft-rotor":      (0.6, 1.7),
    "ship":                (0.3, 4.0),
    "storage-depot":       (0.7, 1.5),    # round → ~square
    "harbor":              (0.2, 5.0),    # very elongated, accept wide range
    "bridge":              (0.1, 8.0),
}

# Per-class minimum-confidence floor below which we always suspect OOD.
# Above this the detection is plausibly correct; below, it's marginal.
CONF_FLOOR: dict[str, float] = {
    "small-vehicle":       0.40,
    "large-vehicle":       0.45,
    "aircraft-fixed-wing": 0.55,
    "aircraft-rotor":      0.50,
    "ship":                0.55,
    "storage-depot":       0.50,
    "harbor":              0.55,
    "bridge":              0.55,
}

OOD_THRESHOLD = 0.55  # ood_score above this → ood_flag = true
EDGE_DENSITY_FLOOR = 0.04  # below this fraction of edge pixels → suspect background


@dataclass
class OodResult:
    score: float
    flagged: bool
    reasons: list[str]


def _aspect_score(class_name: str, x1: float, y1: float, x2: float, y2: float) -> tuple[float, bool]:
    """Returns (score 0..1, triggered?). 1.0 means very anomalous aspect."""
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    aspect = w / h
    lo, hi = TYPICAL_ASPECT.get(class_name, (0.2, 5.0))
    if aspect < lo:
        # how far below lo, normalised
        return min(1.0, (lo - aspect) / lo), True
    if aspect > hi:
        return min(1.0, (aspect - hi) / hi), True
    return 0.0, False


def _conf_score(class_name: str, confidence: float) -> tuple[float, bool]:
    """Low confidence relative to the per-class floor → high OOD score."""
    floor = CONF_FLOOR.get(class_name, 0.45)
    if confidence >= floor:
        return 0.0, False
    # Normalise into [0,1]: at confidence 0 → 1, at floor → 0
    return float((floor - confidence) / max(floor, 1e-3)), True


def _edge_density(image_bgr: np.ndarray, x1: float, y1: float, x2: float, y2: float) -> float:
    """Fraction of bbox pixels that are Canny edges. Real objects (vehicles,
    aircraft, ships) have detail; a flat background blob doesn't."""
    h, w = image_bgr.shape[:2]
    cx0 = max(0, int(round(x1))); cy0 = max(0, int(round(y1)))
    cx1 = min(w, int(round(x2))); cy1 = min(h, int(round(y2)))
    if cx1 - cx0 < 4 or cy1 - cy0 < 4:
        return 0.0
    crop = image_bgr[cy0:cy1, cx0:cx1]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 180)
    return float((edges > 0).sum()) / float(edges.size)


def _edge_score(density: float) -> tuple[float, bool]:
    """Below EDGE_DENSITY_FLOOR → suspect background."""
    if density >= EDGE_DENSITY_FLOOR:
        return 0.0, False
    return min(1.0, (EDGE_DENSITY_FLOOR - density) / EDGE_DENSITY_FLOOR), True


def _heuristic(
    image_bgr: np.ndarray,
    class_name: str,
    confidence: float,
    x1: float, y1: float, x2: float, y2: float,
) -> OodResult:
    """R2 baseline: low_conf + aspect + edge_density signals."""
    reasons: list[str] = []
    s_conf, t_conf = _conf_score(class_name, confidence)
    if t_conf:
        reasons.append(f"low_conf({confidence:.2f})")
    s_aspect, t_aspect = _aspect_score(class_name, x1, y1, x2, y2)
    if t_aspect:
        w, h = x2 - x1, y2 - y1
        reasons.append(f"aspect({w/max(h,1):.2f})")
    density = _edge_density(image_bgr, x1, y1, x2, y2)
    s_edge, t_edge = _edge_score(density)
    if t_edge:
        reasons.append(f"flat_region({density:.3f})")
    score = float(0.45 * s_conf + 0.35 * s_aspect + 0.20 * s_edge)
    return OodResult(
        score=round(score, 4),
        flagged=score >= OOD_THRESHOLD,
        reasons=reasons,
    )


def _mahalanobis(
    image_bgr: np.ndarray,
    class_name: str,
    confidence: float,
    x1: float, y1: float, x2: float, y2: float,
) -> OodResult | None:
    """T1.3 Mahalanobis backend. Returns None if calibration absent or
    feature extraction fails — caller should then fall through to the
    heuristic."""
    calib = ood_calib.load()
    if calib is None:
        return None
    feat = ood_calib.extract_features(image_bgr, confidence, x1, y1, x2, y2)
    if feat is None:
        return None
    res = ood_calib.score(calib, class_name, feat)
    if res is None:
        # Class wasn't in the calibration set — fall through to heuristic.
        return None
    reasons: list[str] = []
    if res.flagged:
        reasons.append(f"mahalanobis(d2={res.distance:.1f} > tau={res.threshold:.1f})")
    return OodResult(
        score=round(res.score, 4),
        flagged=res.flagged,
        reasons=reasons,
    )


def assess_detection(
    image_bgr: np.ndarray,
    class_name: str,
    confidence: float,
    x1: float, y1: float, x2: float, y2: float,
) -> OodResult:
    """Compute an OOD assessment for a single detection.

    Backend selection:
      ASTRA_OOD_BACKEND=mahalanobis (default) — try Mahalanobis first;
        fall back to heuristic if calibration is absent or class unknown.
      ASTRA_OOD_BACKEND=heuristic — skip Mahalanobis, use heuristic only.
    """
    if OOD_BACKEND == "mahalanobis":
        m = _mahalanobis(image_bgr, class_name, confidence, x1, y1, x2, y2)
        if m is not None:
            return m
    return _heuristic(image_bgr, class_name, confidence, x1, y1, x2, y2)


# ── Optional SAM hook (no-op until weights present) ──────────────────────

def sam_available() -> bool:
    from app.config import MODELS_DIR
    return (MODELS_DIR / "sam_vit_b_01ec64.pth").exists()
