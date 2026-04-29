"""
calibrate_ood.py — fit per-class Gaussian over a 9-D feature vector
extracted from each detection's bbox crop. Feeds T1.3 Mahalanobis OOD.

Source of in-distribution samples: the production Postgres detections
table. Detections with valid bbox + intact source image are used. We
sample the most-recent N detections per class (default 200) for balance.

Usage (from repo root):
    D:/astra-data/venvs/astra/Scripts/python.exe scripts/calibrate_ood.py
    D:/astra-data/venvs/astra/Scripts/python.exe scripts/calibrate_ood.py --per-class 500 --percentile 99

Writes:
    D:/astra-data/weights/astra-v1.ood.npz       (numpy NPZ)
    D:/astra-data/weights/astra-v1.ood.meta.json (human-readable summary)
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

# Bootstrap: enable `from app...` imports when invoked from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal             # noqa: E402
from app.db.models import Detection, Mission        # noqa: E402
from app.inference.ood_calib import (               # noqa: E402
    extract_features, fit, save, OOD_WEIGHTS_PATH,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class", type=int, default=200,
                    help="Max detections sampled per class (most recent first)")
    ap.add_argument("--percentile", type=float, default=99.0,
                    help="In-distribution percentile for the OOD threshold")
    args = ap.parse_args()

    db = SessionLocal()

    # Sample by class — most recent first.
    classes = db.query(Detection.class_name).distinct().all()
    classes = [c[0] for c in classes if c[0]]
    print(f"[calibrate] {len(classes)} classes seen: {classes}")

    feats_per_class: dict[str, list[np.ndarray]] = defaultdict(list)
    skipped_no_image = 0
    skipped_bbox = 0
    skipped_class_full = 0

    for cls in classes:
        rows = (
            db.query(Detection)
            .filter(Detection.class_name == cls)
            .order_by(Detection.id.desc())
            .limit(args.per_class * 4)  # pull extra; many will fail crop
            .all()
        )
        for d in rows:
            if len(feats_per_class[cls]) >= args.per_class:
                skipped_class_full += 1
                break
            mission = db.get(Mission, d.mission_id)
            if mission is None or not mission.source_path:
                continue
            src = Path(mission.source_path)
            if not src.exists():
                skipped_no_image += 1
                continue
            img = cv2.imread(str(src), cv2.IMREAD_COLOR)
            if img is None:
                skipped_no_image += 1
                continue
            feat = extract_features(img, d.confidence, d.x1, d.y1, d.x2, d.y2)
            if feat is None:
                skipped_bbox += 1
                continue
            feats_per_class[cls].append(feat)

    sizes = {c: len(v) for c, v in feats_per_class.items()}
    print(f"[calibrate] sampled per class: {sizes}")
    if skipped_no_image or skipped_bbox:
        print(f"[calibrate] skipped: no_image={skipped_no_image} bbox_too_small={skipped_bbox}")

    n_total = sum(sizes.values())
    if n_total < 20:
        print("[calibrate] too few samples — ingest more missions and re-run.")
        sys.exit(1)

    # Drop classes with <2 samples (can't fit covariance contribution well).
    feats_per_class = {c: v for c, v in feats_per_class.items() if len(v) >= 2}
    print(f"[calibrate] fitting over {len(feats_per_class)} classes, {sum(len(v) for v in feats_per_class.values())} samples")

    calib = fit(feats_per_class, percentile=args.percentile)
    save(calib)
    print(f"[calibrate] wrote {OOD_WEIGHTS_PATH}")
    print(f"[calibrate] thresholds (P{args.percentile:.0f}):")
    for cls, tau in zip(calib.classes.tolist(), calib.thresholds.tolist()):
        n = int(calib.n_samples[calib.class_index(cls) or 0])
        print(f"  {cls:<22} tau={tau:7.2f}  n={n}")


if __name__ == "__main__":
    main()
