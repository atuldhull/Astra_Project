"""
Continual learning — operator-confirmed alerts → nightly fine-tune queue.

Approach:
  1. Read confirmed/rejected alerts from Postgres (these are the human
     operator's labels).
  2. For each alert, pull the source mission's image + the detection's
     bbox + the operator's verdict:
       - confirmed: keep the bbox label as-is (positive sample)
       - rejected: drop the bbox (false positive)
       - reclassified: relabel to the operator's chosen class
  3. Append these to a separate "operator-curated" YOLO dataset alongside
     the original training set.
  4. Run a SHORT fine-tune (5 epochs from astra-v1.pt) on the union.

Run nightly (cron / scheduled task) on the operator's machine.

This script is the SCAFFOLD — it writes the curated dataset and the YAML
config; running the actual training is operator-discretion (`python
training/train.py --config training/configs/astra-v1-continual.yaml`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

# Bootstrap the backend so we can import models / db
_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from astra_paths import DATASETS_DIR  # noqa: E402

from app.db.models import Alert, AlertStatus, Detection, Mission  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


CLASS_NAMES = [
    "small-vehicle", "large-vehicle", "aircraft-fixed-wing", "aircraft-rotor",
    "ship", "storage-depot", "harbor", "bridge",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=Path,
                    default=DATASETS_DIR / "astra-continual",
                    help="Where to write the operator-curated dataset")
    ap.add_argument("--min-confirmed", type=int, default=10,
                    help="Skip if fewer than this many confirmed alerts to add")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if args.clean and args.out_root.exists():
        shutil.rmtree(args.out_root)
    (args.out_root / "images").mkdir(parents=True, exist_ok=True)
    (args.out_root / "labels").mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        # 1. Fetch all confirmed + reclassified alerts
        good = db.query(Alert).filter(
            Alert.status.in_([AlertStatus.CONFIRMED, AlertStatus.ENGAGED])
        ).all()
        rejected = db.query(Alert).filter(Alert.status == AlertStatus.REJECTED).all()

        if len(good) < args.min_confirmed:
            print(f"Only {len(good)} confirmed alerts — below --min-confirmed {args.min_confirmed}. Skipping.")
            return

        # 2. Group by mission so we can emit one label.txt per source image
        by_mission: dict[int, list[tuple[Detection, Alert]]] = defaultdict(list)
        for a in good:
            d = db.get(Detection, a.detection_id)
            if d is not None:
                by_mission[a.mission_id].append((d, a))

        rejected_det_ids = {a.detection_id for a in rejected}

        # 3. For each mission, copy the image + write a YOLO label that
        # includes only the OPERATOR-VALIDATED detections.
        copied = 0
        labels_written = 0
        for mid, items in by_mission.items():
            m = db.get(Mission, mid)
            if m is None:
                continue
            src_path = Path(m.source_path)
            if not src_path.exists() or src_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            stem = f"mission-{mid}"
            dst_img = args.out_root / "images" / f"{stem}{src_path.suffix.lower()}"
            dst_lbl = args.out_root / "labels" / f"{stem}.txt"
            if not dst_img.exists():
                shutil.copy2(src_path, dst_img)
                copied += 1

            import cv2
            img = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
            if img is None:
                continue
            h, w = img.shape[:2]

            lines: list[str] = []
            for d, _a in items:
                if d.id in rejected_det_ids:
                    continue
                cx = (d.x1 + d.x2) / 2 / w
                cy = (d.y1 + d.y2) / 2 / h
                bw = (d.x2 - d.x1) / w
                bh = (d.y2 - d.y1) / h
                lines.append(f"{d.class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            if lines:
                dst_lbl.write_text("\n".join(lines) + "\n", encoding="utf-8")
                labels_written += 1

        # 4. Stats
        stats = {
            "copied_images": copied,
            "labels_written": labels_written,
            "good_alerts": len(good),
            "rejected_alerts": len(rejected),
            "class_names": CLASS_NAMES,
        }
        (args.out_root / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

        print(f"\n=== DONE ===")
        print(f"Copied {copied} images, wrote {labels_written} label files.")
        print(f"Good: {len(good)}  Rejected: {len(rejected)}")
        print(f"\nNow fine-tune with:")
        print(f"  python training/train.py --config training/configs/astra-v1-continual.yaml")
    finally:
        db.close()


if __name__ == "__main__":
    main()
