"""
capture_detector_map.py — run YOLO val on the production detector and
write per-class AP + headline mAP@0.5 / mAP@0.5:0.95 to a JSON file the
frontend hero stat reads.

Output: benchmarks/detector_val.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ultralytics import YOLO

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astra_paths import WEIGHTS_DIR, resolve_data_yaml  # noqa: E402

WEIGHTS = WEIGHTS_DIR / "astra-v1.pt"
DATASET_YAML = resolve_data_yaml(REPO_ROOT / "training" / "dataset.yaml")
OUT = REPO_ROOT / "benchmarks" / "detector_val.json"


def main() -> None:
    if not WEIGHTS.exists():
        raise SystemExit(f"weights not found: {WEIGHTS}")
    if not DATASET_YAML.exists():
        raise SystemExit(f"dataset.yaml not found: {DATASET_YAML}")

    print(f"[map] loading {WEIGHTS}")
    model = YOLO(str(WEIGHTS))

    print(f"[map] running val on {DATASET_YAML}")
    metrics = model.val(
        data=str(DATASET_YAML),
        split="val",
        save_json=False,
        conf=0.001,
        iou=0.6,
        verbose=False,
    )

    per_class: list[dict] = []
    for i, ap in enumerate(metrics.box.maps):
        per_class.append({
            "class_id": int(i),
            "class_name": model.names.get(i, f"class-{i}"),
            "ap_50_95": round(float(ap), 4),
        })

    # Paths are recorded relative to their root — this file is committed, and
    # an absolute path here leaks whoever's machine last ran the benchmark.
    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "weights": f"weights/{WEIGHTS.name}",
        "dataset": "training/dataset.yaml",
        "split": "val",
        "map_50": round(float(metrics.box.map50), 4),
        "map_50_95": round(float(metrics.box.map), 4),
        "precision": round(float(metrics.box.mp), 4),
        "recall": round(float(metrics.box.mr), 4),
        "per_class": per_class,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2))
    print(f"[map] wrote {OUT}")
    print(f"[map] mAP@0.5      : {summary['map_50']}")
    print(f"[map] mAP@0.5:0.95 : {summary['map_50_95']}")
    print(f"[map] precision    : {summary['precision']}")
    print(f"[map] recall       : {summary['recall']}")


if __name__ == "__main__":
    main()
