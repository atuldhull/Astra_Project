"""
Measure inference latency of the ASTRA model on CPU (ONNX Runtime) and GPU
(PyTorch). Writes results to docs/benchmark-report.md for the /benchmark
page and the pitch deck.

Usage:
    python benchmark.py \
        --pt D:/astra-data/runs/astra-v1/weights/best.pt \
        --onnx D:/astra-data/weights/astra-v1.onnx \
        --imgsz 1024 --iters 100
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np


def bench_pytorch_gpu(weights: Path, imgsz: int, iters: int) -> dict:
    import torch
    from ultralytics import YOLO

    if not torch.cuda.is_available():
        return {"available": False, "reason": "CUDA not available"}

    model = YOLO(str(weights))
    model.to("cuda:0")
    dummy = np.random.randint(0, 255, (imgsz, imgsz, 3), dtype=np.uint8)

    # Warmup
    for _ in range(10):
        _ = model.predict(dummy, imgsz=imgsz, device=0, verbose=False)

    torch.cuda.synchronize()
    times_ms: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        _ = model.predict(dummy, imgsz=imgsz, device=0, verbose=False)
        torch.cuda.synchronize()
        times_ms.append((time.perf_counter() - t0) * 1000)

    return {
        "available": True,
        "device": torch.cuda.get_device_name(0),
        "mean_ms": round(statistics.mean(times_ms), 2),
        "median_ms": round(statistics.median(times_ms), 2),
        "p95_ms": round(float(np.percentile(times_ms, 95)), 2),
        "fps_median": round(1000 / statistics.median(times_ms), 1),
        "iters": iters,
    }


def bench_onnx_cpu(onnx_path: Path, imgsz: int, iters: int) -> dict:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp_name = sess.get_inputs()[0].name
    dummy = np.random.rand(1, 3, imgsz, imgsz).astype(np.float32)

    for _ in range(5):
        _ = sess.run(None, {inp_name: dummy})

    times_ms: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        _ = sess.run(None, {inp_name: dummy})
        times_ms.append((time.perf_counter() - t0) * 1000)

    return {
        "provider": "CPUExecutionProvider",
        "mean_ms": round(statistics.mean(times_ms), 2),
        "median_ms": round(statistics.median(times_ms), 2),
        "p95_ms": round(float(np.percentile(times_ms, 95)), 2),
        "fps_median": round(1000 / statistics.median(times_ms), 1),
        "iters": iters,
    }


def write_report(results: dict, out_path: Path) -> None:
    lines = ["# ASTRA v1 — Benchmark Report", ""]
    lines.append(f"**imgsz:** {results['imgsz']}  |  **iterations:** {results['iters']}")
    lines.append("")
    lines.append("## GPU (PyTorch + CUDA)")
    gpu = results["gpu"]
    if gpu.get("available"):
        lines.append(f"- Device: **{gpu['device']}**")
        lines.append(f"- Mean latency: **{gpu['mean_ms']} ms/frame**")
        lines.append(f"- Median latency: {gpu['median_ms']} ms")
        lines.append(f"- p95 latency: {gpu['p95_ms']} ms")
        lines.append(f"- Throughput (median): **{gpu['fps_median']} FPS**")
    else:
        lines.append(f"- not available ({gpu.get('reason', 'unknown')})")
    lines.append("")
    lines.append("## CPU (ONNX Runtime)")
    cpu = results["cpu"]
    lines.append(f"- Provider: {cpu['provider']}")
    lines.append(f"- Mean latency: **{cpu['mean_ms']} ms/frame**")
    lines.append(f"- Median latency: {cpu['median_ms']} ms")
    lines.append(f"- p95 latency: {cpu['p95_ms']} ms")
    lines.append(f"- Throughput (median): **{cpu['fps_median']} FPS**")
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pt", type=Path, required=True, help="PyTorch checkpoint (.pt)")
    parser.add_argument("--onnx", type=Path, required=True, help="ONNX model")
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--iters", type=int, default=100)
    parser.add_argument(
        "--out", type=Path,
        default=Path(__file__).parent.parent / "docs" / "benchmark-report.md",
    )
    args = parser.parse_args()

    print("Benchmarking GPU (PyTorch)...")
    gpu = bench_pytorch_gpu(args.pt, args.imgsz, args.iters)
    print(f"  {gpu}")

    print("\nBenchmarking CPU (ONNX Runtime)...")
    cpu = bench_onnx_cpu(args.onnx, args.imgsz, args.iters)
    print(f"  {cpu}")

    results = {"imgsz": args.imgsz, "iters": args.iters, "gpu": gpu, "cpu": cpu}
    write_report(results, args.out)

    json_path = args.out.with_suffix(".json")
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"JSON:   {json_path}")


if __name__ == "__main__":
    main()
