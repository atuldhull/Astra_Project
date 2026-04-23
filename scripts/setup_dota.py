"""
Extract DOTA-v1.5 zips from the staging area and sort every file into
the correct train/val split, regardless of how the user organized the zips.

How it works:
  1. Scan staging/ recursively for .zip files
  2. Identify the TWO "labelTxt-v1.5" label zips — the one found under a
     path containing 'tra' is train-labels, the one under a path containing
     'val' is val-labels. These are authoritative.
  3. Extract label zips → build a stem→split map from the .txt filenames
  4. Extract all remaining (image) zips into a single temp area
  5. For every PNG/TIF found in the temp area, look up its stem in the map
     and move it to out/{train,val}/images/
  6. Move the extracted labels to out/{train,val}/labelTxt/

Run:
    python scripts/setup_dota.py

Staging layout tolerated:
    D:/astra-data/datasets/dota-staging/
        traning/                      (or training, train, anything with 'tra')
            labelTxt-v1.5-*.zip       <- authoritative train labels
            part1-*.zip               <- train images (maybe)
            ... any other zips ...
        validation/                   (or val, anything with 'val')
            labelTxt-v1.5-*.zip       <- authoritative val labels
            ... any image zips the user mis-placed here will still sort correctly ...

Output: D:/astra-data/datasets/dota-raw/{train,val}/{images,labelTxt}/
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
EXCLUDED_DIR_PARTS_LOWER = {"labeltxt-v1.0", "labeltxt_v1.0"}


def _is_label_zip(path: Path) -> bool:
    return path.suffix.lower() == ".zip" and path.stem.lower().startswith("labeltxt-v1.5")


def _split_of_path(path: Path, staging_root: Path) -> str | None:
    """Return 'train' or 'val' based on where a path sits under staging."""
    try:
        rel_parts = [p.lower() for p in path.relative_to(staging_root).parts]
    except ValueError:
        return None
    for part in rel_parts:
        if part.startswith("val"):
            return "val"
        if part.startswith("tra"):  # 'train', 'training', or the user's typo 'traning'
            return "train"
    return None


def _extract_zip(zip_path: Path, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
        return 1
    except zipfile.BadZipFile:
        print(f"  ! corrupt/incomplete zip, skipping: {zip_path.name}")
        return 0


def _walk_nested_zips(root: Path, dest: Path) -> int:
    """Extract any zips found inside `root` (e.g. Drive-wrapped images-*.zip
    that contain part1.zip). Repeat until no more .zip files remain."""
    extracted = 0
    for _ in range(5):  # cap recursion just in case
        nested = [p for p in root.rglob("*.zip") if p.is_file()]
        if not nested:
            break
        for z in nested:
            print(f"    + nested extract: {z.name}")
            _extract_zip(z, z.parent)
            z.unlink(missing_ok=True)
            extracted += 1
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, default=Path("D:/astra-data/datasets/dota-staging"))
    parser.add_argument("--out", type=Path, default=Path("D:/astra-data/datasets/dota-raw"))
    args = parser.parse_args()

    if not args.staging.exists():
        sys.exit(f"staging dir not found: {args.staging}")

    # Collect every zip under staging.
    all_zips = [p for p in args.staging.rglob("*.zip") if p.is_file()]
    if not all_zips:
        sys.exit(f"no zips found under {args.staging}")

    label_zips: dict[str, Path] = {}          # split → label zip
    image_zips: list[tuple[str | None, Path]] = []

    for z in all_zips:
        split = _split_of_path(z, args.staging)
        if _is_label_zip(z):
            if split is None:
                print(f"! label zip at unknown split, skipping: {z}")
                continue
            if split in label_zips:
                print(f"! multiple label zips for {split}; keeping first: {label_zips[split].name}, ignoring {z.name}")
                continue
            label_zips[split] = z
        else:
            image_zips.append((split, z))

    if "train" not in label_zips:
        sys.exit("no train label zip found (expected labelTxt-v1.5-*.zip inside a training/ folder)")
    if "val" not in label_zips:
        sys.exit("no val label zip found (expected labelTxt-v1.5-*.zip inside a validation/ folder)")

    print(f"label zips:")
    for split, z in label_zips.items():
        print(f"  {split:5s} <- {z.relative_to(args.staging)}")
    print(f"image zips: {len(image_zips)} file(s)")
    for _, z in image_zips:
        print(f"  <- {z.relative_to(args.staging)} ({z.stat().st_size / (1024*1024):,.0f} MB)")

    # Prepare output dirs.
    for split in ("train", "val"):
        (args.out / split / "images").mkdir(parents=True, exist_ok=True)
        (args.out / split / "labelTxt").mkdir(parents=True, exist_ok=True)

    # Work in a temp dir alongside the output (same drive → fast moves).
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dota-extract-", dir=str(args.out)) as tmp:
        tmp_root = Path(tmp)

        # ── 1. Extract label zips and build stem → split map ────────────────
        stem_to_split: dict[str, str] = {}
        for split, z in label_zips.items():
            print(f"\nExtracting {split} labels: {z.name}")
            ldir = tmp_root / f"labels-{split}"
            _extract_zip(z, ldir)
            # Google Drive often wraps the real labelTxt-v1.5.zip inside another
            # zip, so recursively unwrap until only plain files remain.
            _walk_nested_zips(ldir, ldir)
            for txt in ldir.rglob("*.txt"):
                if any(part.lower() in EXCLUDED_DIR_PARTS_LOWER for part in txt.parts):
                    continue
                stem_to_split[txt.stem] = split
                # Move into final location while we're here.
                dest_lbl = args.out / split / "labelTxt" / txt.name
                if not dest_lbl.exists():
                    shutil.move(str(txt), str(dest_lbl))
        print(f"\nLabel stems: {sum(1 for v in stem_to_split.values() if v == 'train')} train / "
              f"{sum(1 for v in stem_to_split.values() if v == 'val')} val")

        # ── 2. Extract all image zips into one pool ─────────────────────────
        print(f"\nExtracting {len(image_zips)} image zip(s)...")
        pool = tmp_root / "image-pool"
        pool.mkdir(exist_ok=True)
        for split_hint, z in image_zips:
            print(f"  [{split_hint or '?':5s}] {z.name} ({z.stat().st_size / (1024*1024):,.0f} MB)")
            _extract_zip(z, pool)
        _walk_nested_zips(pool, pool)

        # ── 3. Walk pool, dispatch each image to its real split by stem ─────
        counts = {"train": 0, "val": 0, "orphan": 0}
        for img in pool.rglob("*"):
            if not img.is_file() or img.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            split = stem_to_split.get(img.stem)
            if split is None:
                counts["orphan"] += 1
                continue
            dest = args.out / split / "images" / img.name
            if dest.exists():
                continue
            shutil.move(str(img), str(dest))
            counts[split] += 1

        print(f"\nImages placed: train={counts['train']}, val={counts['val']}, orphan={counts['orphan']}")

    # ── 4. Final counts ─────────────────────────────────────────────────────
    final = {}
    for split in ("train", "val"):
        imgs = list((args.out / split / "images").glob("*"))
        lbls = list((args.out / split / "labelTxt").glob("*.txt"))
        final[split] = (len(imgs), len(lbls))

    print("\n=== DONE ===")
    for split, (n_img, n_lbl) in final.items():
        print(f"{split:5s}: {n_img} images / {n_lbl} labels")
    print(f"\noutput: {args.out}")
    print("\nNext: python training/prepare_dota.py")


if __name__ == "__main__":
    main()
