"""
Generate FGSM-perturbed copies of a sample of training tiles.

The purpose is "adversarial data augmentation for free" — we run the
existing astra-v1 detector to compute the gradient direction that would
fool it most, perturb the image in that direction, and save the result as
a NEW training tile alongside the original. The next training run sees
both the clean and adversarial versions, learning to be robust to the
same perturbations.

Usage:
    python training/adversarial_augment.py \\
        --weights $ASTRA_DATA_DIR/runs/astra-v1-2/weights/best.pt \\
        --train-images $ASTRA_DATA_DIR/datasets/astra-v1/images/train \\
        --train-labels $ASTRA_DATA_DIR/datasets/astra-v1/labels/train \\
        --fraction 0.30 --epsilon 0.04 --clean-existing

After this completes, run the hardened training:
    python training/train.py --config training/configs/astra-v1-hardened.yaml

Then promote the resulting weights so the backend can find them:
    cp $ASTRA_DATA_DIR/runs/astra-v1-hardened/weights/best.pt \\
       $ASTRA_DATA_DIR/weights/astra-v1-hardened.pt
"""

from __future__ import annotations

import argparse
import random
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np


# We reuse the inference adversarial perturb function — it already knows how
# to letterbox to 640², compute the gradient on the YOLO head's class scores,
# and unwrap back to the original size.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from astra_paths import DATASETS_DIR, RUNS_DIR, WEIGHTS_DIR  # noqa: E402
from app.inference.adversarial import perturb_fgsm  # noqa: E402


ADVERSARIAL_SUFFIX = "__adv"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, default=RUNS_DIR / "astra-v1-2" / "weights" / "best.pt",
                    help="YOLOv11 weights to compute the gradient against")
    ap.add_argument("--train-images", type=Path,
                    default=DATASETS_DIR / "astra-v1" / "images" / "train")
    ap.add_argument("--train-labels", type=Path,
                    default=DATASETS_DIR / "astra-v1" / "labels" / "train")
    ap.add_argument("--fraction", type=float, default=0.30,
                    help="Fraction of training tiles to augment (0..1)")
    ap.add_argument("--epsilon", type=float, default=0.04,
                    help="FGSM perturbation strength")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0,
                    help="Hard cap on number of tiles to augment (0 = no cap)")
    ap.add_argument("--clean-existing", action="store_true",
                    help="Delete previously generated *__adv.{jpg,txt} before running")
    args = ap.parse_args()

    if not args.weights.exists():
        sys.exit(f"Weights not found: {args.weights}")
    if not args.train_images.exists():
        sys.exit(f"Train images dir not found: {args.train_images}")
    if not args.train_labels.exists():
        sys.exit(f"Train labels dir not found: {args.train_labels}")

    if args.clean_existing:
        n = 0
        for p in args.train_images.glob(f"*{ADVERSARIAL_SUFFIX}.jpg"):
            p.unlink(); n += 1
        for p in args.train_labels.glob(f"*{ADVERSARIAL_SUFFIX}.txt"):
            p.unlink(); n += 1
        print(f"Cleaned {n} previously-generated adversarial files")

    rng = random.Random(args.seed)
    all_tiles = sorted(p for p in args.train_images.iterdir()
                       if p.suffix.lower() == ".jpg" and ADVERSARIAL_SUFFIX not in p.stem)
    print(f"Found {len(all_tiles)} clean training tiles")

    n_pick = int(round(len(all_tiles) * args.fraction))
    if args.limit > 0:
        n_pick = min(n_pick, args.limit)
    chosen = rng.sample(all_tiles, n_pick)
    print(f"Picking {n_pick} tiles to perturb at ε={args.epsilon}")

    # Load YOLO once.
    from ultralytics import YOLO
    yolo = YOLO(str(args.weights))

    t0 = time.time()
    written = 0
    failed = 0
    for i, src_img_path in enumerate(chosen, 1):
        src_lbl_path = args.train_labels / f"{src_img_path.stem}.txt"
        if not src_lbl_path.exists():
            continue
        img = cv2.imread(str(src_img_path), cv2.IMREAD_COLOR)
        if img is None:
            failed += 1
            continue
        try:
            adv = perturb_fgsm(yolo, img, args.epsilon)
        except Exception as exc:
            failed += 1
            if failed < 5:
                print(f"  [warn] FGSM failed on {src_img_path.name}: {exc}")
            continue

        out_img = args.train_images / f"{src_img_path.stem}{ADVERSARIAL_SUFFIX}.jpg"
        out_lbl = args.train_labels / f"{src_lbl_path.stem}{ADVERSARIAL_SUFFIX}.txt"
        cv2.imwrite(str(out_img), adv, [cv2.IMWRITE_JPEG_QUALITY, 92])
        shutil.copyfile(src_lbl_path, out_lbl)
        written += 1

        if i % 50 == 0:
            rate = i / (time.time() - t0)
            eta = (n_pick - i) / max(rate, 0.01)
            print(f"  [{i}/{n_pick}]  written={written}  failed={failed}  {rate:.1f} tiles/s  ETA {eta:.0f}s")

    elapsed = time.time() - t0
    print(f"\n=== DONE ===")
    print(f"Wrote {written} adversarial tile pairs in {elapsed:.0f}s ({written/max(elapsed,1):.2f} tiles/s)")
    if failed:
        print(f"Failed on {failed} tiles (silently skipped)")
    print(f"\nNext step:")
    print(f"  python training/train.py --config training/configs/astra-v1-hardened.yaml")
    print(f"\nThen promote the hardened weights:")
    print(f"  cp {RUNS_DIR}/astra-v1-hardened/weights/best.pt \\")
    print(f"     {WEIGHTS_DIR}/astra-v1-hardened.pt")


if __name__ == "__main__":
    main()
