"""
Convert the MAR20 dataset (Military Aircraft Recognition, 20 fine-grained
variants) from PASCAL-VOC XML annotations into a YOLO **classification**
dataset of cropped aircraft images.

Why classification, not detection:
  Stage 1 of ASTRA's cascade is the existing DOTA-trained YOLOv11n detector
  (gives a generic "aircraft-fixed-wing" box). Stage 2 takes that crop and
  classifies it into one of MAR20's 20 specific airframes (Su-35, F-22, ...).
  A YOLO-cls model trained on crops is exactly the right tool: small input,
  one prediction per image, no anchor/assigner overhead.

The user must download MAR20 manually (registration on the authors' page):
    https://gcheng-nwpu.github.io/#Datasets

Expected input layout (canonical PASCAL VOC — confirmed against the
upstream MAR20 release):
    $ASTRA_DATA_DIR/datasets/MAR20/
        JPEGImages/                                  *.jpg     (3,842 files)
        Annotations/Horizontal Bounding Boxes/       *.xml     (preferred, 3,842)
        Annotations/Oriented Bounding Boxes/         *.xml     (ignored — we use HBB)
        Annotations/                                 *.xml     (fallback if flattened)
        ImageSets/Main/
            train.txt                                 (1,330 stems → our train)
            test.txt                                  (2,510 stems → our val)

Output layout (Ultralytics YOLO-cls standard):
    $ASTRA_DATA_DIR/datasets/mar20-cls/
        train/<airframe>/<stem>__<idx>.jpg
        val/<airframe>/<stem>__<idx>.jpg
        stats.json

If train.txt/test.txt are absent we fall back to a deterministic 85/15
per-class split.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astra_paths import DATASETS_DIR  # noqa: E402

# MAR20 stores classes as A1..A20. The paper assigns each code to a specific
# airframe; we use those names so the UI can render them human-readably
# instead of "A14".
#
# Source: Yu et al., "MAR20: A Benchmark for Military Aircraft Recognition
# in Remote Sensing Images", National Remote Sensing Bulletin, 2023.
MAR20_CLASS_MAP: dict[str, str] = {
    "A1":  "SU-35",
    "A2":  "C-130",
    "A3":  "C-17",
    "A4":  "C-5",
    "A5":  "F-16",
    "A6":  "TU-160",
    "A7":  "E-3",
    "A8":  "B-52",
    "A9":  "P-3C",
    "A10": "B-1B",
    "A11": "E-8",
    "A12": "TU-22",
    "A13": "F-15",
    "A14": "KC-135",
    "A15": "F-22",
    "A16": "FA-18",
    "A17": "TU-95",
    "A18": "KC-10",
    "A19": "SU-34",
    "A20": "SU-24",
}

# How much padding to add around each bbox before cropping (fraction of
# bbox size). Aircraft tail/wingtip often pokes outside the tight box and
# fine-grained features (engine count, vertical stabilizer shape) live there.
CROP_PAD_FRAC = 0.15

# Discard crops smaller than this (probably a labelling artefact).
MIN_CROP_SIDE_PX = 24

JPEG_QUALITY = 95


def find_annotations_dir(root: Path) -> Path:
    """Find the directory that holds the .xml files. The MAR20 release uses
    'Annotations/Horizontal Bounding Boxes/' nested, but some redistributions
    flatten it. Try both."""
    candidates = [
        root / "Annotations" / "Horizontal Bounding Boxes",
        root / "Annotations" / "HorizontalBoundingBoxes",
        root / "Annotations" / "horizontal",
        root / "Annotations",
    ]
    for c in candidates:
        if c.exists() and any(c.glob("*.xml")):
            return c
    raise SystemExit(
        f"Couldn't find MAR20 annotations under {root}.\n"
        f"Looked in: {[str(c) for c in candidates]}\n"
        f"Expected *.xml VOC files."
    )


def read_split_list(splits_dir: Path, name: str) -> set[str] | None:
    """Read ImageSets/Main/<name>.txt → set of stems. Returns None if absent."""
    f = splits_dir / f"{name}.txt"
    if not f.exists():
        return None
    return {
        line.strip()
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    }


def parse_voc_xml(xml_path: Path) -> list[tuple[str, int, int, int, int]]:
    """Return list of (class_code, xmin, ymin, xmax, ymax). Skips boxes whose
    class code isn't in MAR20_CLASS_MAP (defensive: shouldn't happen in
    canonical MAR20)."""
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return []
    root = tree.getroot()
    boxes: list[tuple[str, int, int, int, int]] = []
    for obj in root.findall("object"):
        name_elem = obj.find("name")
        bb = obj.find("bndbox")
        if name_elem is None or bb is None:
            continue
        cls_code = (name_elem.text or "").strip()
        if cls_code not in MAR20_CLASS_MAP:
            continue
        try:
            xmin = int(float(bb.findtext("xmin", "0")))
            ymin = int(float(bb.findtext("ymin", "0")))
            xmax = int(float(bb.findtext("xmax", "0")))
            ymax = int(float(bb.findtext("ymax", "0")))
        except ValueError:
            continue
        if xmax <= xmin or ymax <= ymin:
            continue
        boxes.append((cls_code, xmin, ymin, xmax, ymax))
    return boxes


def crop_with_pad(
    img,
    xmin: int, ymin: int, xmax: int, ymax: int,
    pad_frac: float,
):
    """Crop (xmin, ymin, xmax, ymax) from img with `pad_frac` of bbox size
    added on each side, clipped to image bounds."""
    h, w = img.shape[:2]
    bw = xmax - xmin
    bh = ymax - ymin
    pad_x = int(round(bw * pad_frac))
    pad_y = int(round(bh * pad_frac))
    x0 = max(0, xmin - pad_x)
    y0 = max(0, ymin - pad_y)
    x1 = min(w, xmax + pad_x)
    y1 = min(h, ymax + pad_y)
    return img[y0:y1, x0:x1]


def deterministic_split(stems: list[str], val_frac: float = 0.15) -> tuple[set[str], set[str]]:
    """Sort by stem, every Nth → val. Reproducible across runs without RNG."""
    stems_sorted = sorted(stems)
    step = max(2, int(round(1 / val_frac)))
    val = {s for i, s in enumerate(stems_sorted) if i % step == 0}
    train = {s for s in stems_sorted if s not in val}
    return train, val


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert MAR20 → YOLO-cls cropped dataset")
    parser.add_argument(
        "--mar20-root", type=Path,
        default=DATASETS_DIR / "MAR20",
        help="Root of unpacked MAR20 (must contain JPEGImages/ and Annotations/)",
    )
    parser.add_argument(
        "--out-root", type=Path,
        default=DATASETS_DIR / "mar20-cls",
        help="Output classification dataset root",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Wipe the output directory before writing",
    )
    parser.add_argument(
        "--pad", type=float, default=CROP_PAD_FRAC,
        help=f"Bbox padding fraction (default {CROP_PAD_FRAC})",
    )
    args = parser.parse_args()

    img_dir = args.mar20_root / "JPEGImages"
    if not img_dir.exists():
        raise SystemExit(f"Missing {img_dir}. Download MAR20 from https://gcheng-nwpu.github.io/#Datasets")

    ann_dir = find_annotations_dir(args.mar20_root)
    splits_dir = args.mar20_root / "ImageSets" / "Main"

    if args.clean and args.out_root.exists():
        print(f"Wiping {args.out_root}")
        shutil.rmtree(args.out_root)

    # Pre-create class subfolders for both splits so YOLO-cls is happy even
    # if a class ends up empty in val (it won't, but defensive).
    for split in ("train", "val"):
        for airframe in MAR20_CLASS_MAP.values():
            (args.out_root / split / airframe).mkdir(parents=True, exist_ok=True)

    # Determine which stems go where.
    upstream_train = read_split_list(splits_dir, "train")
    upstream_test = read_split_list(splits_dir, "test")
    all_stems = sorted(p.stem for p in img_dir.glob("*.jpg"))

    if upstream_train is not None and upstream_test is not None:
        print(f"Using upstream MAR20 splits: train={len(upstream_train)}, test={len(upstream_test)}")
        train_stems = upstream_train & set(all_stems)
        val_stems = upstream_test & set(all_stems)
    else:
        print("No upstream split found — using deterministic 85/15 split")
        train_stems_set, val_stems_set = deterministic_split(all_stems, val_frac=0.15)
        train_stems = train_stems_set
        val_stems = val_stems_set

    print(f"Total images: {len(all_stems)}  (train={len(train_stems)}, val={len(val_stems)})")

    counts: dict[str, dict[str, int]] = {
        "train": defaultdict(int),
        "val": defaultdict(int),
    }
    crop_total = 0
    skipped_small = 0

    for idx, stem in enumerate(sorted(all_stems), 1):
        split = "train" if stem in train_stems else "val" if stem in val_stems else None
        if split is None:
            continue  # stem listed in JPEGImages but in neither split — skip

        img_path = img_dir / f"{stem}.jpg"
        xml_path = ann_dir / f"{stem}.xml"
        boxes = parse_voc_xml(xml_path)
        if not boxes:
            continue

        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            print(f"  [skip] unreadable: {img_path.name}")
            continue

        for box_idx, (cls_code, xmin, ymin, xmax, ymax) in enumerate(boxes):
            crop = crop_with_pad(img, xmin, ymin, xmax, ymax, args.pad)
            if crop.shape[0] < MIN_CROP_SIDE_PX or crop.shape[1] < MIN_CROP_SIDE_PX:
                skipped_small += 1
                continue
            airframe = MAR20_CLASS_MAP[cls_code]
            out_path = args.out_root / split / airframe / f"{stem}__{box_idx:02d}.jpg"
            cv2.imwrite(str(out_path), crop, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            counts[split][airframe] += 1
            crop_total += 1

        if idx % 200 == 0:
            print(f"  [{idx}/{len(all_stems)}] crops written: {crop_total}")

    stats = {
        "class_codes": MAR20_CLASS_MAP,
        "class_names": sorted(MAR20_CLASS_MAP.values()),
        "splits": {
            split: dict(sorted(counts[split].items())) for split in ("train", "val")
        },
        "totals": {
            "train_crops": sum(counts["train"].values()),
            "val_crops": sum(counts["val"].values()),
            "all_crops": crop_total,
            "skipped_too_small_px": skipped_small,
        },
        "crop_pad_frac": args.pad,
        "min_crop_side_px": MIN_CROP_SIDE_PX,
    }
    stats_path = args.out_root / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print("\n=== DONE ===")
    print(f"Train crops: {stats['totals']['train_crops']}")
    print(f"Val crops:   {stats['totals']['val_crops']}")
    print(f"Skipped (too small): {skipped_small}")
    print("\nPer-airframe (train / val):")
    for airframe in sorted(MAR20_CLASS_MAP.values()):
        t = counts["train"].get(airframe, 0)
        v = counts["val"].get(airframe, 0)
        print(f"  {airframe:8s}  {t:5d} / {v:4d}")
    print(f"\nStats written to {stats_path}")
    print(f"\nNext step:  python train.py --config configs/astra-aircraft-v1.yaml")


if __name__ == "__main__":
    main()
