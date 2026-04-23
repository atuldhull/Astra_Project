"""
Threat scoring formula — see PROJECT_SPEC.md §8.

threat_score =
      w_class  * class_weight[cls]
    + w_prox   * exp(-distance_km / 5.0)
    + w_motion * movement_toward_asset_score   (0..1)
    + w_count  * log(1 + count_of_same_class_in_aoi)
    + w_conf   * detection_confidence

Result is clamped to [0, 1] for sortable UI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ── Defaults (commander can override at runtime via /api/v1/weights) ──────

DEFAULT_CLASS_WEIGHTS: dict[str, float] = {
    "small-vehicle": 0.30,
    "large-vehicle": 0.60,
    "aircraft-fixed-wing": 0.90,
    "aircraft-rotor": 0.80,
    "ship": 0.70,
    "storage-depot": 0.50,
    "harbor": 0.45,
    "bridge": 0.55,
}

DEFAULT_WEIGHTS = {
    "w_class": 0.35,
    "w_prox": 0.25,
    "w_motion": 0.20,
    "w_count": 0.10,
    "w_conf": 0.10,
}


@dataclass(frozen=True)
class ScoreInputs:
    class_name: str
    confidence: float
    distance_km: float | None = None          # None → proximity term is 0
    movement_toward_asset: float = 0.0         # 0..1
    same_class_count_in_aoi: int = 1           # >=1


@dataclass(frozen=True)
class ScoreResult:
    score: float                       # final 0..1 threat score
    class_term: float
    proximity_term: float
    motion_term: float
    count_term: float
    confidence_term: float


def compute_threat_score(
    inputs: ScoreInputs,
    *,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    class_weights: dict[str, float] = DEFAULT_CLASS_WEIGHTS,
) -> ScoreResult:
    class_w = class_weights.get(inputs.class_name, 0.3)
    class_term = weights["w_class"] * class_w

    if inputs.distance_km is None:
        proximity_term = 0.0
    else:
        proximity_term = weights["w_prox"] * math.exp(-max(0.0, inputs.distance_km) / 5.0)

    motion_term = weights["w_motion"] * max(0.0, min(1.0, inputs.movement_toward_asset))
    count_term = weights["w_count"] * math.log(1 + max(0, inputs.same_class_count_in_aoi - 1))
    confidence_term = weights["w_conf"] * max(0.0, min(1.0, inputs.confidence))

    raw = class_term + proximity_term + motion_term + count_term + confidence_term
    # Clamp to [0, 1]. The formula can technically exceed 1 for dense clusters,
    # but we want a sortable/comparable UI score.
    score = max(0.0, min(1.0, raw))

    return ScoreResult(
        score=score,
        class_term=class_term,
        proximity_term=proximity_term,
        motion_term=motion_term,
        count_term=count_term,
        confidence_term=confidence_term,
    )
