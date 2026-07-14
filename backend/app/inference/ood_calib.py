"""
Mahalanobis OOD calibration.

Per-class Gaussian model over a 9-dimensional model-agnostic feature
vector extracted from each detection's bbox crop:

    [aspect_ratio, area_norm, conf,
     mean_R, mean_G, mean_B,
     std_intensity, edge_density, hue_entropy]

For each class c we fit:
    μ_c    — class mean (9,)
    Σ_pool — pooled covariance (9, 9)        # shared across classes
    inv_Σ  — pseudo-inverse of Σ_pool          (9, 9)

Mahalanobis distance for a test point x predicted as class c:
    D²(x, c) = (x - μ_c)ᵀ Σ⁻¹ (x - μ_c)

A per-class threshold τ_c is set at the 99th percentile of in-distribution
distances seen during calibration. Detections with D² > τ_c are flagged.

Why pooled (shared) Σ instead of per-class Σ:
  Per-class covariance fails when n_c is small (we may have <30 samples
  for rare classes like aircraft-rotor). Pooled covariance trades a bit
  of class-specificity for stability — standard Lee 2018 practice.

Why these features, not YOLO penultimate-layer features:
  Penultimate features require model surgery + a forward hook on the
  detector. v3.0 ships the model-agnostic primitive; the same fit/score
  code accepts richer features by changing one extractor function. A
  Round-4 task can swap to penultimate features without touching the
  rest of the pipeline.

Persistence: NPZ at OOD_WEIGHTS_PATH, gzipped via numpy.savez_compressed.
Schema: classes (k,), mu (k, 9), inv_cov (9, 9), thresholds (k,),
        n_samples_per_class (k,), feature_names (9,), captured_at (str).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.config import WEIGHTS_DIR


OOD_WEIGHTS_PATH = Path(
    os.environ.get("ASTRA_OOD_WEIGHTS") or WEIGHTS_DIR / "astra-v1.ood.npz"
)
OOD_META_PATH = OOD_WEIGHTS_PATH.with_suffix(".meta.json")

FEATURE_NAMES = [
    "aspect_ratio", "area_norm", "confidence",
    "mean_R", "mean_G", "mean_B",
    "std_intensity", "edge_density", "hue_entropy",
]
N_FEATS = len(FEATURE_NAMES)


# ── Feature extraction ─────────────────────────────────────────────────

def extract_features(
    image_bgr: np.ndarray,
    confidence: float,
    x1: float, y1: float, x2: float, y2: float,
) -> np.ndarray | None:
    """Returns a 9-D feature vector or None if the bbox is unusable."""
    H, W = image_bgr.shape[:2]
    cx0 = max(0, int(round(x1))); cy0 = max(0, int(round(y1)))
    cx1 = min(W, int(round(x2))); cy1 = min(H, int(round(y2)))
    if cx1 - cx0 < 4 or cy1 - cy0 < 4:
        return None

    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    aspect = float(w / h)
    area_norm = float((w * h) / max(W * H, 1.0))

    crop = image_bgr[cy0:cy1, cx0:cx1]
    # OpenCV uses BGR. Save mean of each channel as RGB ordering for
    # downstream readability. Normalize to [0, 1].
    mean_b, mean_g, mean_r = (crop.reshape(-1, 3).mean(axis=0) / 255.0).tolist()

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    std_int = float(gray.std() / 255.0)

    edges = cv2.Canny(gray, 60, 180)
    edge_density = float((edges > 0).sum()) / float(max(edges.size, 1))

    # Hue entropy — texture in color space
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0], None, [16], [0, 180]).flatten()
    p = hist / max(hist.sum(), 1.0)
    p = p[p > 0]
    hue_entropy = float(-np.sum(p * np.log2(p))) if p.size else 0.0
    # Normalize to ~[0,1] (max entropy of 16-bin histogram is log2(16)=4).
    hue_entropy_norm = hue_entropy / 4.0

    return np.array([
        aspect, area_norm, float(confidence),
        mean_r, mean_g, mean_b,
        std_int, edge_density, hue_entropy_norm,
    ], dtype=np.float64)


# ── Fitting ────────────────────────────────────────────────────────────

@dataclass
class Calibration:
    classes: np.ndarray             # (k,) class names
    mu: np.ndarray                  # (k, 9)
    inv_cov: np.ndarray             # (9, 9) pooled
    thresholds: np.ndarray          # (k,) 99th percentile in-dist distance
    n_samples: np.ndarray           # (k,) per-class sample counts
    captured_at: str

    def class_index(self, name: str) -> int | None:
        """Returns the index of `name` in `self.classes`, or None."""
        idxs = np.where(self.classes == name)[0]
        return int(idxs[0]) if idxs.size > 0 else None


def fit(features_per_class: dict[str, list[np.ndarray]], percentile: float = 99.0) -> Calibration:
    """Fit per-class means + pooled covariance + per-class thresholds."""
    from datetime import datetime, timezone

    classes_list: list[str] = sorted(features_per_class.keys())
    if not classes_list:
        raise ValueError("no classes provided to fit")

    mu_rows: list[np.ndarray] = []
    n_rows: list[int] = []
    centered_chunks: list[np.ndarray] = []

    for cls in classes_list:
        feats = np.stack(features_per_class[cls], axis=0)  # (n, 9)
        if feats.shape[0] < 2:
            # Single sample — can't compute covariance contribution. Use mu only.
            mu = feats[0]
            mu_rows.append(mu)
            n_rows.append(int(feats.shape[0]))
            continue
        mu = feats.mean(axis=0)
        mu_rows.append(mu)
        n_rows.append(int(feats.shape[0]))
        centered_chunks.append(feats - mu)

    if not centered_chunks:
        raise ValueError("not enough samples in any class to fit covariance")

    centered_all = np.concatenate(centered_chunks, axis=0)
    cov = np.cov(centered_all, rowvar=False)
    # Add small ridge for invertibility on small samples.
    cov = cov + np.eye(N_FEATS) * 1e-6
    inv_cov = np.linalg.pinv(cov)

    mu_arr = np.stack(mu_rows, axis=0)        # (k, 9)
    n_arr = np.array(n_rows, dtype=np.int64)  # (k,)

    # Per-class threshold = percentile of in-distribution Mahalanobis distances.
    thresholds = np.zeros(len(classes_list), dtype=np.float64)
    for i, cls in enumerate(classes_list):
        feats = np.stack(features_per_class[cls], axis=0)
        diffs = feats - mu_arr[i]
        d2 = np.einsum("ij,jk,ik->i", diffs, inv_cov, diffs)
        thresholds[i] = float(np.percentile(d2, percentile)) if d2.size else 0.0

    return Calibration(
        classes=np.array(classes_list, dtype=object),
        mu=mu_arr,
        inv_cov=inv_cov,
        thresholds=thresholds,
        n_samples=n_arr,
        captured_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Persistence ────────────────────────────────────────────────────────

def save(c: Calibration, path: Path = OOD_WEIGHTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        classes=c.classes,
        mu=c.mu,
        inv_cov=c.inv_cov,
        thresholds=c.thresholds,
        n_samples=c.n_samples,
        feature_names=np.array(FEATURE_NAMES, dtype=object),
        captured_at=np.array(c.captured_at),
    )
    OOD_META_PATH.write_text(json.dumps({
        "captured_at": c.captured_at,
        "n_classes": int(c.classes.size),
        "feature_names": FEATURE_NAMES,
        "n_samples_per_class": dict(zip(c.classes.tolist(), c.n_samples.tolist())),
        "thresholds": dict(zip(c.classes.tolist(), c.thresholds.tolist())),
    }, indent=2))


_cached: Calibration | None = None


def load(path: Path = OOD_WEIGHTS_PATH) -> Calibration | None:
    global _cached
    if _cached is not None:
        return _cached
    if not path.exists():
        return None
    z = np.load(path, allow_pickle=True)
    _cached = Calibration(
        classes=z["classes"],
        mu=z["mu"],
        inv_cov=z["inv_cov"],
        thresholds=z["thresholds"],
        n_samples=z["n_samples"],
        captured_at=str(z["captured_at"]),
    )
    return _cached


def clear_cache() -> None:
    global _cached
    _cached = None


# ── Scoring ────────────────────────────────────────────────────────────

@dataclass
class MahalanobisResult:
    distance: float       # Mahalanobis squared distance to class mean
    threshold: float      # in-distribution 99th percentile for that class
    score: float          # normalised 0..1 (distance / threshold), clipped to 1
    flagged: bool


def score(
    calib: Calibration,
    class_name: str,
    feat: np.ndarray,
) -> MahalanobisResult | None:
    idx = calib.class_index(class_name)
    if idx is None:
        return None
    diff = feat - calib.mu[idx]
    d2 = float(diff @ calib.inv_cov @ diff)
    tau = float(calib.thresholds[idx])
    norm = min(1.0, d2 / tau) if tau > 0 else 0.0
    return MahalanobisResult(
        distance=d2,
        threshold=tau,
        score=norm,
        flagged=d2 > tau,
    )


def status() -> dict:
    """For /api/v1/ood/calibration."""
    calib = load()
    if calib is None:
        return {
            "available": False,
            "weights_path": str(OOD_WEIGHTS_PATH),
            "hint": "run scripts/calibrate_ood.py to fit calibration",
        }
    return {
        "available": True,
        "weights_path": str(OOD_WEIGHTS_PATH),
        "captured_at": calib.captured_at,
        "feature_names": FEATURE_NAMES,
        "classes": calib.classes.tolist(),
        "n_samples_per_class": dict(zip(calib.classes.tolist(), calib.n_samples.tolist())),
        "thresholds": dict(zip(calib.classes.tolist(), [float(t) for t in calib.thresholds])),
    }
