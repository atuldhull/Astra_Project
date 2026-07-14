"""
Launch YOLOv11 training for ASTRA v1.

Usage:
    python train.py --config configs/astra-v1.yaml
    python train.py --config configs/astra-v1.yaml --smoke-test

--smoke-test runs 1 epoch on the first 50 images to verify the pipeline
end-to-end before committing to the full overnight run.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astra_paths import expand, resolve_data_yaml, tokenize  # noqa: E402


def load_config(path: Path) -> dict:
    """Load a training YAML, expanding ${ASTRA_DATA_DIR} in every string value."""
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {k: expand(v) if isinstance(v, str) else v for k, v in cfg.items()}


def ensure_cuda() -> None:
    try:
        import torch
    except ImportError:
        sys.exit("PyTorch is not installed. Run: pip install -r backend/requirements-cuda.txt")
    if not torch.cuda.is_available():
        sys.exit(
            "CUDA is not available to PyTorch.\n"
            "Expected: RTX 4050 Laptop GPU on driver 581.83.\n"
            "Run `nvidia-smi` to confirm the GPU is visible, and reinstall the cu124 wheels."
        )
    print(f"CUDA OK: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory // (1024**3)}GB)")


def make_smoke_subset(dataset_yaml: Path, n_images: int = 50) -> Path:
    """Create a tiny copy of the dataset yaml pointing to the first N images.
    Used by --smoke-test to validate the pipeline in ~2 minutes."""
    cfg = yaml.safe_load(dataset_yaml.read_text(encoding="utf-8"))
    root = Path(cfg["path"])
    smoke_root = root.parent / f"{root.name}-smoke"
    smoke_root.mkdir(parents=True, exist_ok=True)

    for split in ("train", "val"):
        src_img = root / "images" / split
        src_lbl = root / "labels" / split
        dst_img = smoke_root / "images" / split
        dst_lbl = smoke_root / "labels" / split
        dst_img.mkdir(parents=True, exist_ok=True)
        dst_lbl.mkdir(parents=True, exist_ok=True)
        images = sorted(src_img.glob("*.jpg"))[:n_images]
        for img in images:
            lbl = src_lbl / f"{img.stem}.txt"
            shutil.copy2(img, dst_img / img.name)
            if lbl.exists():
                shutil.copy2(lbl, dst_lbl / lbl.name)
        print(f"  smoke [{split}] copied {len(images)} images")

    # Written back with the ${ASTRA_DATA_DIR} token — this file is committed.
    smoke_cfg = {**cfg, "path": tokenize(str(smoke_root).replace("\\", "/"))}
    smoke_yaml = dataset_yaml.parent / "dataset-smoke.yaml"
    smoke_yaml.write_text(yaml.safe_dump(smoke_cfg, sort_keys=False), encoding="utf-8")
    return resolve_data_yaml(smoke_yaml)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True, help="Path to training config YAML")
    parser.add_argument("--smoke-test", action="store_true", help="1-epoch run on 50 images to validate pipeline")
    parser.add_argument("--resume", action="store_true", help="Resume from the last run")
    args = parser.parse_args()

    ensure_cuda()

    cfg = load_config(args.config)
    # Resolve `data:` relative to the config file's directory, not the CWD.
    data_path = Path(cfg["data"])
    if not data_path.is_absolute():
        data_path = (args.config.parent / data_path).resolve()
    if not data_path.exists():
        sys.exit(f"dataset.yaml not found at {data_path}. Run prepare_dota.py first.")
    # Ultralytics reads the dataset YAML itself and won't expand our token.
    data_yaml = resolve_data_yaml(data_path)
    cfg["data"] = str(data_yaml)

    # Ultralytics imports torch, so delay this until after ensure_cuda() gives a clean message.
    from ultralytics import YOLO

    # Apply smoke-test overrides.
    if args.smoke_test:
        print("\n=== SMOKE TEST MODE — 1 epoch, 50 images, no augmentation ===\n")
        smoke_yaml = make_smoke_subset(data_yaml, n_images=50)
        cfg = {
            **cfg,
            "data": str(smoke_yaml),
            "epochs": 1,
            "patience": 0,
            "name": f"{cfg.get('name', 'astra')}-smoke",
            "mosaic": 0.0,
            "mixup": 0.0,
            "copy_paste": 0.0,
            "cache": False,
            "plots": False,
        }

    model_name = cfg.pop("model")
    print(f"\nLoading base model: {model_name}")
    model = YOLO(model_name)

    print(f"\nTraining config:")
    for k, v in cfg.items():
        print(f"  {k}: {v}")
    print()

    results = model.train(**cfg, resume=args.resume)
    print(f"\n=== Training finished ===")
    print(f"Best weights: {results.save_dir}/weights/best.pt")


if __name__ == "__main__":
    main()
