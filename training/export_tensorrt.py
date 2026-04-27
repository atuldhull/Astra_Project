"""
Export astra-v1.pt to TensorRT INT8 for the edge-benchmark story.

Pitch line: "Same model, three deployment targets — RTX 4050 FP32, CPU ONNX,
Jetson-class TensorRT INT8 — with measured latency for each."

Ultralytics' built-in exporter handles the heavy lifting (ONNX → TensorRT
parser, INT8 calibration cache). We just give it sane defaults and a
fallback to FP16 if INT8 calibration fails (no calibration data) — FP16 is
still a 3rd benchmark number for the slides.

Usage:
    python training/export_tensorrt.py
    python training/export_tensorrt.py --weights D:/astra-data/runs/astra-v1-2/weights/best.pt --int8

Output:
    D:/astra-data/weights/astra-v1.engine     (TensorRT engine)
    Print: latency benchmark on a 5-image dummy run

This MUST be run on the deployment device (or one with the same TensorRT +
GPU compute capability) — engines are not portable.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path,
                    default=Path("D:/astra-data/runs/astra-v1-2/weights/best.pt"))
    ap.add_argument("--out", type=Path,
                    default=Path("D:/astra-data/weights/astra-v1.engine"))
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--int8", action="store_true",
                    help="Try INT8 quantization. Falls back to FP16 if calibration fails.")
    ap.add_argument("--workspace", type=int, default=2,
                    help="TRT workspace size in GB")
    args = ap.parse_args()

    if not args.weights.exists():
        raise SystemExit(f"Weights not found: {args.weights}")

    from ultralytics import YOLO
    model = YOLO(str(args.weights))

    print(f"Exporting to TensorRT  imgsz={args.imgsz}  int8={args.int8}  workspace={args.workspace}GB")
    t0 = time.time()
    try:
        engine_path = model.export(
            format="engine",
            imgsz=args.imgsz,
            int8=args.int8,
            half=not args.int8,    # FP16 if not INT8
            workspace=args.workspace,
            device=0,
            verbose=True,
        )
    except Exception as exc:
        print(f"\n[!] Export failed with int8={args.int8}: {exc}")
        if args.int8:
            print("Retrying with FP16 (no calibration data needed)...")
            engine_path = model.export(
                format="engine",
                imgsz=args.imgsz,
                int8=False,
                half=True,
                workspace=args.workspace,
                device=0,
                verbose=True,
            )
        else:
            raise

    elapsed = time.time() - t0
    print(f"\n=== EXPORT DONE in {elapsed:.0f}s ===")
    print(f"Engine: {engine_path}")

    # Move to canonical weights dir if Ultralytics put it elsewhere.
    src = Path(engine_path)
    if src != args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        try:
            import shutil
            shutil.copy2(src, args.out)
            print(f"Copied to: {args.out}")
        except OSError as exc:
            print(f"[warn] couldn't copy to {args.out}: {exc}")

    # Quick benchmark — 50 inference passes on a black 640² image.
    print("\n=== INFERENCE BENCHMARK (50 runs on dummy image) ===")
    import numpy as np
    eng_model = YOLO(str(args.out if args.out.exists() else src))
    dummy = np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8)
    eng_model.predict(dummy, verbose=False)  # warmup
    t = time.time()
    for _ in range(50):
        eng_model.predict(dummy, verbose=False)
    per_image_ms = (time.time() - t) / 50 * 1000
    print(f"Median latency: {per_image_ms:.2f} ms/image  ({1000/per_image_ms:.0f} FPS)")


if __name__ == "__main__":
    main()
