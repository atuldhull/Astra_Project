# MAR20 dataset — operator setup notes

**Used by:** Round 2 cascade — fine-grained military airframe classifier (Day 1, hours 0-10).

## What MAR20 is

20-class military aircraft recognition benchmark from NWPU (Northwestern
Polytechnical University, Xi'an). Top-down aerial photos sourced from Google
Earth, ~3,842 images, ~22,341 annotated airframe instances. PASCAL-VOC XML
annotations.

**Class codes → airframes** (Yu et al., NRSB 2023):

| Code | Airframe | Code | Airframe |
|------|----------|------|----------|
| A1   | SU-35    | A11  | E-8      |
| A2   | C-130    | A12  | TU-22    |
| A3   | C-17     | A13  | F-15     |
| A4   | C-5      | A14  | KC-135   |
| A5   | F-16     | A15  | F-22     |
| A6   | TU-160   | A16  | FA-18    |
| A7   | E-3      | A17  | TU-95    |
| A8   | B-52     | A18  | KC-10    |
| A9   | P-3C     | A19  | SU-34    |
| A10  | B-1B     | A20  | SU-24    |

## Where to get it

Authors' release page (registration may be required, light):
**https://gcheng-nwpu.github.io/#Datasets**

Look for the **MAR20** entry. The download is typically a Baidu Pan link
(China) or a Google Drive mirror. If Baidu is blocked, try the GitHub
mirrors: `github.com/topics/mar20` typically lists at least one redistribution.

Approximate size: ~1.2 GB compressed.

## Where to put it

Unpack so the layout is exactly (this matches the upstream release as
verified against the actual extracted contents — 3,842 JPEGs, 3,842 HBB
XMLs, train/test split files present):

```
$ASTRA_DATA_DIR/datasets/MAR20/
    JPEGImages/                                   *.jpg     (3,842 files)
    Annotations/
        Horizontal Bounding Boxes/                *.xml     (preferred — 3,842)
        Oriented Bounding Boxes/                  *.xml     (ignored)
    ImageSets/Main/
        train.txt                                  (1,330 stems → our train)
        test.txt                                   (2,510 stems → our val)
```

`prepare_mar20.py` will autodetect either annotation layout. If
`ImageSets/Main/{train,test}.txt` are missing it falls back to a
deterministic 85/15 split.

## Then run

```bash
# 1) Convert VOC XML → YOLO-classification crops
python training/prepare_mar20.py --clean

# 2) Train the airframe classifier (~6 hours background on RTX 4050)
python training/train.py --config training/configs/astra-aircraft-v1.yaml
```

Output classifier weights: `$ASTRA_DATA_DIR/runs/astra-aircraft-v1/weights/best.pt`

## If download is blocked

**Plan B** (per `docs/round2-warplan.md` risk matrix): synthesize fine-grained
labels by clustering DOTA `plane` crops (no real airframe IDs, but visually
distinct sub-clusters with synthetic names like "Type-A", "Type-B"). Demoable
but weaker — only fall back if MAR20 cannot be obtained.
