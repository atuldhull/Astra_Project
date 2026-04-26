"""
Split the MAR20 cls TRAIN folder into N disjoint per-client subfolders, in
the same per-class layout YOLO-cls / torchvision.ImageFolder expects.

Three split modes:
  iid       — uniform random shuffle, every class is roughly equally
              represented in every client. Easy mode.
  non-iid   — each client gets a biased class distribution. Models a real
              "geographic" split where one base sees mostly transports,
              another mostly fighters.
  attack    — like iid, but ALSO writes a poisoned shadow client whose
              labels are systematically wrong (e.g. F-22 -> SU-24). Used
              for the FoolsGold demo.

Output layout:
    out_root/
        node-0/<airframe>/*.jpg     (links or copies)
        node-1/<airframe>/*.jpg
        node-2/<airframe>/*.jpg
        [poison/<airframe>/*.jpg]   (only with --mode attack)

We HARDLINK by default (cheap on NTFS/ext4) so disk usage doesn't blow up.
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
from collections import defaultdict
from pathlib import Path


def link_or_copy(src: Path, dst: Path) -> None:
    """Create a hardlink from src -> dst; fall back to copy on error
    (cross-device, or filesystem that doesn't support links)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def collect_per_class(train_root: Path) -> dict[str, list[Path]]:
    """Walk train_root/<class>/*.jpg and return {class: [paths]} sorted."""
    out: dict[str, list[Path]] = {}
    for cls_dir in sorted(p for p in train_root.iterdir() if p.is_dir()):
        out[cls_dir.name] = sorted(cls_dir.glob("*.jpg"))
    return out


def iid_split(per_class: dict[str, list[Path]], n_nodes: int, seed: int) -> list[dict[str, list[Path]]]:
    """Round-robin per-class split → every node sees every class evenly."""
    rng = random.Random(seed)
    nodes: list[dict[str, list[Path]]] = [defaultdict(list) for _ in range(n_nodes)]
    for cls, paths in per_class.items():
        shuffled = paths[:]
        rng.shuffle(shuffled)
        for i, p in enumerate(shuffled):
            nodes[i % n_nodes][cls].append(p)
    return nodes


def non_iid_split(per_class: dict[str, list[Path]], n_nodes: int, seed: int, alpha: float = 0.3) -> list[dict[str, list[Path]]]:
    """Dirichlet-α split: each class is split across nodes per a random
    Dirichlet-α distribution. Smaller α → more skewed per-class coverage."""
    import numpy as np
    rng = np.random.default_rng(seed)
    nodes: list[dict[str, list[Path]]] = [defaultdict(list) for _ in range(n_nodes)]
    for cls, paths in per_class.items():
        if not paths:
            continue
        shuffled = paths[:]
        rng.shuffle(shuffled)
        proportions = rng.dirichlet([alpha] * n_nodes)
        # Cumulative cut points
        cuts = (proportions.cumsum() * len(shuffled)).astype(int)
        cuts[-1] = len(shuffled)  # ensure all imgs are placed
        prev = 0
        for i, c in enumerate(cuts):
            for p in shuffled[prev:c]:
                nodes[i][cls].append(p)
            prev = c
    return nodes


def write_split(node_assignments: list[dict[str, list[Path]]], out_root: Path, prefix: str = "node") -> dict:
    """Write each node's assignment as a per-class folder of hardlinks."""
    counts: dict[str, dict[str, int]] = {}
    for i, assignment in enumerate(node_assignments):
        nid = f"{prefix}-{i}"
        counts[nid] = {}
        for cls, paths in assignment.items():
            for src in paths:
                dst = out_root / nid / cls / src.name
                link_or_copy(src, dst)
            counts[nid][cls] = len(paths)
    return counts


def write_poison_node(per_class: dict[str, list[Path]], out_root: Path, label_swap: dict[str, str], n_per_class: int, seed: int) -> dict:
    """Write a poison client. For each (src_class, target_class) pair in
    `label_swap`, copy n_per_class images from src_class but PUT them in
    the target_class folder. The model sees mislabeled examples."""
    rng = random.Random(seed)
    nid = "poison"
    counts: dict[str, int] = {}
    for src_cls, tgt_cls in label_swap.items():
        if src_cls not in per_class:
            continue
        chosen = rng.sample(per_class[src_cls], min(n_per_class, len(per_class[src_cls])))
        for src in chosen:
            dst = out_root / nid / tgt_cls / f"poison_{src_cls}_to_{tgt_cls}_{src.name}"
            link_or_copy(src, dst)
        counts[f"{src_cls}->{tgt_cls}"] = len(chosen)
    return {nid: counts}


def main() -> None:
    ap = argparse.ArgumentParser(description="Partition MAR20-cls train into N federated nodes")
    ap.add_argument("--train-root", type=Path, default=Path("D:/astra-data/datasets/mar20-cls/train"))
    ap.add_argument("--out-root", type=Path, default=Path("D:/astra-data/datasets/mar20-cls-fed"))
    ap.add_argument("--nodes", type=int, default=3)
    ap.add_argument("--mode", choices=["iid", "non-iid", "attack"], default="non-iid")
    ap.add_argument("--alpha", type=float, default=0.3, help="Dirichlet alpha for non-iid mode")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--clean", action="store_true", help="Wipe out-root first")
    args = ap.parse_args()

    if not args.train_root.exists():
        raise SystemExit(
            f"Missing {args.train_root}. Run training/prepare_mar20.py first."
        )
    if args.clean and args.out_root.exists():
        print(f"Wiping {args.out_root}")
        shutil.rmtree(args.out_root)

    per_class = collect_per_class(args.train_root)
    print(f"Source: {args.train_root}")
    print(f"  classes: {len(per_class)}")
    total = sum(len(p) for p in per_class.values())
    print(f"  images: {total}")

    if args.mode == "iid":
        nodes = iid_split(per_class, args.nodes, args.seed)
    else:
        nodes = non_iid_split(per_class, args.nodes, args.seed, alpha=args.alpha)
    counts = write_split(nodes, args.out_root)

    poison_counts: dict = {}
    if args.mode == "attack":
        # Honest demo swaps: F-22 <-> SU-24 (visually distinct, dramatic).
        # If those classes don't exist in this MAR20 release, fall back to
        # the first two alphabetically.
        cls_list = sorted(per_class.keys())
        if "F-22" in cls_list and "SU-24" in cls_list:
            swap = {"F-22": "SU-24", "SU-24": "F-22"}
        else:
            swap = {cls_list[0]: cls_list[1], cls_list[1]: cls_list[0]}
        print(f"Attack mode: poisoning with swap {swap}")
        poison_counts = write_poison_node(per_class, args.out_root, swap, n_per_class=80, seed=args.seed)

    # Write a summary stats file the dashboard / runner can read.
    import json
    stats = {
        "mode": args.mode,
        "nodes": args.nodes,
        "classes": sorted(per_class.keys()),
        "node_counts": counts,
        "poison_counts": poison_counts,
    }
    (args.out_root / "split-stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"\nWrote split to {args.out_root}")
    for nid, cnts in counts.items():
        print(f"  {nid}: {sum(cnts.values())} images across {len(cnts)} classes")
    if poison_counts:
        for nid, cnts in poison_counts.items():
            print(f"  {nid}: {cnts}")


if __name__ == "__main__":
    main()
