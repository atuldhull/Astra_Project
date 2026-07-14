"""
Export a trained ASTRA YOLO checkpoint to ONNX for CPU-side inference
and for the /benchmark page.

Usage:
    python export_onnx.py --weights $ASTRA_DATA_DIR/runs/astra-v1/weights/best.pt
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astra_paths import WEIGHTS_DIR  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True, help="Path to .pt checkpoint")
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--out", type=Path, default=WEIGHTS_DIR / "astra-v1.onnx")
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--dynamic", action="store_true", help="Dynamic batch dimension")
    parser.add_argument("--half", action="store_true", help="FP16 export (GPU only)")
    args = parser.parse_args()

    if not args.weights.exists():
        raise SystemExit(f"weights not found: {args.weights}")

    from ultralytics import YOLO

    model = YOLO(str(args.weights))
    onnx_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        opset=args.opset,
        dynamic=args.dynamic,
        half=args.half,
        simplify=True,
    )
    onnx_path = Path(onnx_path)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(onnx_path, args.out)

    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"\nExported: {args.out}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
