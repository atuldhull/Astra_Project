"""
Out-of-distribution gatekeeper.

Goal: flag YOLO detections that are likely *not* one of the 8 DOTA classes
the model was trained on. The model has no "unknown" label, so it confidently
mis-labels alien objects (a building roof as a ship, a tennis court as a
storage depot). Without a gate the demo viewer thinks the model is wrong;
with the gate, the same detection shows as grey-with-"?" and the demo viewer
sees that the system *knew* it didn't know.

We ship two implementations behind one interface:

  * lightweight (default, no downloads, ALWAYS available):
      OOD score per detection from three heuristics:
        - low confidence relative to its class's training-time mean
        - extreme aspect ratio for the claimed class (e.g. a 5:1 ship)
        - low edge density inside the bbox (real DOTA objects have texture)
      Score is in [0,1]; threshold 0.55 → flagged.

  * SAM (optional, opt-in via env var or weight presence):
      Mask the bbox interior with SAM, count distinct components, compare
      with YOLO's expectation. NOT SHIPPED YET — placeholder hook below
      so we can drop in `sam_vit_b` weights tomorrow without UI changes.

Result is stashed into Detection.extras_json as:
    {"ood_score": 0.62, "ood_flag": true, "ood_reasons": ["low_conf", "aspect"]}
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


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


def assess_detection(
    image_bgr: np.ndarray,
    class_name: str,
    confidence: float,
    x1: float, y1: float, x2: float, y2: float,
) -> OodResult:
    """Compute an OOD assessment for a single detection.

    Combines three lightweight signals (conf, aspect, edge-density) into a
    single 0..1 score. Reasons list is human-readable for the UI tooltip."""
    reasons: list[str] = []
    sub_scores: list[float] = []

    s_conf, t_conf = _conf_score(class_name, confidence)
    if t_conf:
        reasons.append(f"low_conf({confidence:.2f})")
    sub_scores.append(s_conf)

    s_aspect, t_aspect = _aspect_score(class_name, x1, y1, x2, y2)
    if t_aspect:
        w, h = x2 - x1, y2 - y1
        reasons.append(f"aspect({w/max(h,1):.2f})")
    sub_scores.append(s_aspect)

    density = _edge_density(image_bgr, x1, y1, x2, y2)
    s_edge, t_edge = _edge_score(density)
    if t_edge:
        reasons.append(f"flat_region({density:.3f})")
    sub_scores.append(s_edge)

    # Weighted combination: low_conf and aspect carry more weight than
    # texture (edge density is noisier).
    score = float(0.45 * s_conf + 0.35 * s_aspect + 0.20 * s_edge)
    return OodResult(
        score=round(score, 4),
        flagged=score >= OOD_THRESHOLD,
        reasons=reasons,
    )


# ── Optional SAM hook (no-op until weights present) ──────────────────────

def sam_available() -> bool:
    from pathlib import Path
    return Path("D:/astra-data/models/sam_vit_b_01ec64.pth").exists()
