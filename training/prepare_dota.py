"""
Convert DOTA-v1.5 raw data into Ultralytics YOLO format for ASTRA v1.

The user must download DOTA-v1.5 manually (registration required):
    https://captain-whu.github.io/DOTA/dataset.html

Expected input layout:
    D:/astra-data/datasets/dota-raw/
        train/
            images/P0001.png ...
            labelTxt/P0001.txt ...
        val/
            images/
            labelTxt/

Output layout (Ultralytics standard):
    D:/astra-data/datasets/astra-v1/
        images/{train,val,test}/*.jpg
        labels/{train,val,test}/*.txt   (YOLO: class cx cy w h, normalized)
        stats.json

Pipeline per image:
  1. Parse oriented bboxes (8 coords + class + difficulty)
  2. Convert to axis-aligned bboxes (min/max of corners)
  3. Filter to the 8-class defence-relevant subset (see PROJECT_SPEC.md §6)
  4. Tile the image into 1024x1024 windows with 20% overlap
  5. For each tile, keep boxes whose center falls inside, clipped to tile
  6. Skip tiles with zero valid boxes
  7. Write tile JPEG + YOLO-format label file

DOTA's val split is partitioned 50/50 into our val/test deterministically
so training sees no val-or-test images.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# ── DOTA → ASTRA class remap ──────────────────────────────────────────────
# Only classes listed here are kept; everything else is dropped.
CLASS_MAP: dict[str, int] = {
    "small-vehicle": 0,
    "large-vehicle": 1,
    "plane": 2,
    "helicopter": 3,
    "ship": 4,
    "storage-tank": 5,
    "harbor": 6,
    "bridge": 7,
}

ASTRA_CLASS_NAMES = [
    "small-vehicle",
    "large-vehicle",
    "aircraft-fixed-wing",
    "aircraft-rotor",
    "ship",
    "storage-depot",
    "harbor",
    "bridge",
]

TILE_SIZE = 1024
TILE_STRIDE = 820  # ~20% overlap
MIN_BOX_AREA_PX = 20  # discard boxes whose area in the tile is this tiny
JPEG_QUALITY = 92


@dataclass
class OBB:
    """DOTA oriented bounding box with 4 corner points."""
    corners: np.ndarray  # shape (4, 2), float
    cls_id: int
    difficulty: int

    @property
    def aabb(self) -> tuple[float, float, float, float]:
        """Axis-aligned bbox as (x1, y1, x2, y2)."""
        x1, y1 = self.corners.min(axis=0)
        x2, y2 = self.corners.max(axis=0)
        return float(x1), float(y1), float(x2), float(y2)


def parse_label_file(path: Path) -> list[OBB]:
    """Parse a DOTA labelTxt file. Silently skips malformed lines and
    classes that aren't in CLASS_MAP."""
    boxes: list[OBB] = []
    if not path.exists():
        return boxes
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split()
        # DOTA format: x1 y1 x2 y2 x3 y3 x4 y4 class difficulty
        # First two lines may be metadata ("imagesource:..." / "gsd:...") — skip those.
        if len(parts) < 10 or not parts[0].replace(".", "").replace("-", "").isdigit():
            continue
        try:
            coords = np.array([float(p) for p in parts[:8]], dtype=np.float32).reshape(4, 2)
            cls_name = parts[8]
            difficulty = int(parts[9]) if parts[9].isdigit() else 0
        except (ValueError, IndexError):
            continue
        if cls_name not in CLASS_MAP:
            continue
        boxes.append(OBB(corners=coords, cls_id=CLASS_MAP[cls_name], difficulty=difficulty))
    return boxes


def tile_image(
    img: np.ndarray,
    boxes: list[OBB],
    tile_size: int,
    stride: int,
) -> list[tuple[np.ndarray, list[tuple[int, float, float, float, float]]]]:
    """Slide a (tile_size x tile_size) window over the image. For each tile,
    return boxes whose AABB center falls inside, with coordinates clipped to
    the tile and converted to YOLO normalized format.

    Returns: list of (tile_bgr, [(cls, cx, cy, w, h), ...]) — only tiles
    with at least one valid box are kept.
    """
    h, w = img.shape[:2]
    # Ensure we cover the right and bottom edges.
    xs = list(range(0, max(1, w - tile_size + 1), stride))
    ys = list(range(0, max(1, h - tile_size + 1), stride))
    if xs[-1] + tile_size < w:
        xs.append(w - tile_size)
    if ys[-1] + tile_size < h:
        ys.append(h - tile_size)
    if w <= tile_size:
        xs = [0]
    if h <= tile_size:
        ys = [0]

    aabbs = [(b.cls_id, *b.aabb) for b in boxes]

    tiles: list[tuple[np.ndarray, list[tuple[int, float, float, float, float]]]] = []
    for y0 in ys:
        for x0 in xs:
            x1, y1 = x0 + tile_size, y0 + tile_size
            # Handle images smaller than tile (pad to tile_size).
            tile = np.zeros((tile_size, tile_size, 3), dtype=img.dtype)
            crop = img[y0:min(y1, h), x0:min(x1, w)]
            tile[: crop.shape[0], : crop.shape[1]] = crop

            yolo_boxes: list[tuple[int, float, float, float, float]] = []
            for cls, bx1, by1, bx2, by2 in aabbs:
                # Center in image coords.
                ccx, ccy = (bx1 + bx2) / 2, (by1 + by2) / 2
                if not (x0 <= ccx < x1 and y0 <= ccy < y1):
                    continue
                # Clip to tile bounds.
                cx1 = max(bx1, x0)
                cy1 = max(by1, y0)
                cx2 = min(bx2, x1)
                cy2 = min(by2, y1)
                bw_px = cx2 - cx1
                bh_px = cy2 - cy1
                if bw_px * bh_px < MIN_BOX_AREA_PX:
                    continue
                # Convert to tile-local normalized YOLO format.
                nx = ((cx1 + cx2) / 2 - x0) / tile_size
                ny = ((cy1 + cy2) / 2 - y0) / tile_size
                nw = bw_px / tile_size
                nh = bh_px / tile_size
                yolo_boxes.append((cls, nx, ny, nw, nh))

            if yolo_boxes:
                tiles.append((tile, yolo_boxes))
    return tiles


def write_yolo_label(path: Path, boxes: list[tuple[int, float, float, float, float]]) -> None:
    lines = [f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cls, cx, cy, w, h in boxes]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process_split(
    src_images_dir: Path,
    src_labels_dir: Path,
    out_images_dir: Path,
    out_labels_dir: Path,
    class_counts: dict[int, int],
    split_name: str,
    image_filter: set[str] | None = None,
) -> int:
    """Returns total tiles written for the split."""
    out_images_dir.mkdir(parents=True, exist_ok=True)
    out_labels_dir.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(
        p for p in src_images_dir.iterdir()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
        and (image_filter is None or p.stem in image_filter)
    )

    total_tiles = 0
    for idx, img_path in enumerate(image_paths, 1):
        label_path = src_labels_dir / f"{img_path.stem}.txt"
        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            print(f"  [skip] unreadable image: {img_path.name}")
            continue
        boxes = parse_label_file(label_path)
        if not boxes:
            continue

        tiles = tile_image(img, boxes, TILE_SIZE, TILE_STRIDE)
        for tile_idx, (tile, yolo_boxes) in enumerate(tiles):
            stem = f"{img_path.stem}__t{tile_idx:03d}"
            out_img = out_images_dir / f"{stem}.jpg"
            out_lbl = out_labels_dir / f"{stem}.txt"
            cv2.imwrite(str(out_img), tile, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            write_yolo_label(out_lbl, yolo_boxes)
            for cls, *_ in yolo_boxes:
                class_counts[cls] = class_counts.get(cls, 0) + 1
            total_tiles += 1

        if idx % 25 == 0:
            print(f"  [{split_name}] {idx}/{len(image_paths)} images → {total_tiles} tiles so far")

    return total_tiles


def split_val_images(val_images_dir: Path) -> tuple[set[str], set[str]]:
    """Deterministic 50/50 split of DOTA's val set into our val + test."""
    stems = sorted(p.stem for p in val_images_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
    half = len(stems) // 2
    # Every even-indexed → val, every odd → test (stable, reproducible).
    our_val = {s for i, s in enumerate(stems) if i % 2 == 0}
    our_test = {s for i, s in enumerate(stems) if i % 2 == 1}
    return our_val, our_test


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert DOTA-v1.5 → ASTRA YOLO format")
    parser.add_argument(
        "--dota-root", type=Path, default=Path("D:/astra-data/datasets/dota-raw"),
        help="Root of unpacked DOTA dataset (must contain train/ and val/)",
    )
    parser.add_argument(
        "--out-root", type=Path, default=Path("D:/astra-data/datasets/astra-v1"),
        help="Output YOLO dataset root",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Wipe the output directory before writing (DANGER: deletes all previous converted data)",
    )
    args = parser.parse_args()

    train_img = args.dota_root / "train" / "images"
    train_lbl = args.dota_root / "train" / "labelTxt"
    val_img = args.dota_root / "val" / "images"
    val_lbl = args.dota_root / "val" / "labelTxt"

    for p in (train_img, train_lbl, val_img, val_lbl):
        if not p.exists():
            raise SystemExit(f"Missing DOTA path: {p}\nDownload DOTA-v1.5 from https://captain-whu.github.io/DOTA/")

    if args.clean and args.out_root.exists():
        print(f"Wiping {args.out_root}")
        shutil.rmtree(args.out_root)

    out_dirs = {
        ("images", "train"): args.out_root / "images" / "train",
        ("images", "val"):   args.out_root / "images" / "val",
        ("images", "test"):  args.out_root / "images" / "test",
        ("labels", "train"): args.out_root / "labels" / "train",
        ("labels", "val"):   args.out_root / "labels" / "val",
        ("labels", "test"):  args.out_root / "labels" / "test",
    }
    for p in out_dirs.values():
        p.mkdir(parents=True, exist_ok=True)

    class_counts: dict[int, int] = {}

    print(f"\n=== TRAIN split ===")
    train_tiles = process_split(
        train_img, train_lbl,
        out_dirs[("images", "train")], out_dirs[("labels", "train")],
        class_counts, "train",
    )

    print(f"\n=== VAL/TEST split (DOTA val → 50/50) ===")
    val_stems, test_stems = split_val_images(val_img)
    val_tiles = process_split(
        val_img, val_lbl,
        out_dirs[("images", "val")], out_dirs[("labels", "val")],
        class_counts, "val", image_filter=val_stems,
    )
    test_tiles = process_split(
        val_img, val_lbl,
        out_dirs[("images", "test")], out_dirs[("labels", "test")],
        class_counts, "test", image_filter=test_stems,
    )

    stats = {
        "class_names": ASTRA_CLASS_NAMES,
        "class_counts": {ASTRA_CLASS_NAMES[cls]: cnt for cls, cnt in sorted(class_counts.items())},
        "tile_counts": {"train": train_tiles, "val": val_tiles, "test": test_tiles},
        "tile_size": TILE_SIZE,
        "tile_stride": TILE_STRIDE,
    }
    stats_path = args.out_root / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print("\n=== DONE ===")
    print(f"Train tiles: {train_tiles}")
    print(f"Val tiles:   {val_tiles}")
    print(f"Test tiles:  {test_tiles}")
    print(f"Class distribution (total instances):")
    for name, cnt in stats["class_counts"].items():
        print(f"  {name:22s}  {cnt}")
    print(f"\nStats written to {stats_path}")


if __name__ == "__main__":
    main()
