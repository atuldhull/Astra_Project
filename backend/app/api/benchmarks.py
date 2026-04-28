"""
/benchmarks endpoint — exposes captured benchmark JSON (mAP, latency,
adversarial retention) so the frontend can render hero stats without
shelling out or shipping the JSON in the bundle.

Files live at REPO_ROOT/benchmarks/*.json and are produced by the
scripts under scripts/. If a file is missing, the endpoint returns
a 200 with `available: false` and a hint for which script to run.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

REPO_ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = REPO_ROOT / "benchmarks"


def _read(name: str, hint: str) -> dict:
    f = BENCH_DIR / name
    if not f.exists():
        return {"available": False, "hint": hint}
    try:
        return {"available": True, **json.loads(f.read_text(encoding="utf-8"))}
    except Exception as exc:
        return {"available": False, "hint": f"{name} unreadable: {exc}"}


@router.get("/detector")
def detector_metrics() -> dict:
    """mAP@0.5 / mAP@0.5:0.95 / P / R / per-class AP."""
    return _read(
        "detector_val.json",
        "run: python scripts/capture_detector_map.py",
    )


@router.get("/latency")
def latency_metrics() -> dict:
    """ingest-to-alert p50 / p95 / p99 over N iterations."""
    return _read(
        "latency.json",
        "run: python scripts/e2e_regression.py --latency",
    )


@router.get("/adversarial")
def adversarial_metrics() -> dict:
    """Baseline vs hardened retention under attack."""
    return _read(
        "adversarial_ab.json",
        "run: python scripts/adversarial_ab.py",
    )
