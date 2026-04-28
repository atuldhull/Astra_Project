"""
capture_latency.py — measure end-to-end ingest → alert latency.

For each iteration:
  1. open WS to /ws/live
  2. POST a demo image to /api/v1/ingest
  3. wait until an alert event for that mission arrives on the WS
  4. record elapsed wall-clock ms

Writes p50 / p95 / p99 / max to benchmarks/latency.json so the Benchmark
hero stat reads it.

Usage:
    python scripts/capture_latency.py --n 20 \
        --image D:/astra-data/demo-samples/02-airfield-hero.jpg
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMAGE = Path("D:/astra-data/demo-samples/02-airfield-hero.jpg")
OUT = REPO_ROOT / "benchmarks" / "latency.json"


async def one_iteration(base: str, ws_url: str, image: Path, timeout_s: float) -> float:
    """Returns elapsed ms from POST /ingest start to first detection event
    (with an associated alert_id) on the WS for that mission. Raises
    asyncio.TimeoutError if no qualifying event arrives inside timeout_s.

    Pipeline broadcasts events with type='detection' that carry an
    alert_id when an Alert was created for that detection — that's what
    we treat as "ingest -> alert" round-trip.
    """
    async with websockets.connect(ws_url) as ws:
        t0 = time.perf_counter()

        async def _ingest() -> int:
            async with httpx.AsyncClient(timeout=30) as client:
                with image.open("rb") as f:
                    r = await client.post(
                        f"{base}/api/v1/ingest",
                        files={"file": (image.name, f, "image/jpeg")},
                        data={"name": f"latency-{int(time.time()*1000)}"},
                    )
                r.raise_for_status()
                return int(r.json()["id"])

        ingest_task = asyncio.create_task(_ingest())
        mission_id: int | None = None

        async def _wait_for_alert() -> float:
            nonlocal mission_id
            while True:
                msg = await ws.recv()
                try:
                    data = json.loads(msg)
                except Exception:
                    continue
                if data.get("type") != "detection":
                    continue
                if data.get("alert_id") is None:
                    continue
                m_id = data.get("mission_id")
                if mission_id is not None and m_id != mission_id:
                    continue
                return (time.perf_counter() - t0) * 1000

        async def _track_ingest() -> None:
            nonlocal mission_id
            mission_id = await ingest_task

        track_task = asyncio.create_task(_track_ingest())
        try:
            elapsed = await asyncio.wait_for(_wait_for_alert(), timeout=timeout_s)
        finally:
            track_task.cancel()
            ingest_task.cancel()
        return elapsed


async def main_async(args: argparse.Namespace) -> int:
    if not args.image.exists():
        print(f"image not found: {args.image}")
        return 1

    samples_ms: list[float] = []
    failures = 0
    for i in range(args.n):
        try:
            ms = await one_iteration(args.base, args.ws, args.image, args.timeout)
            samples_ms.append(ms)
            print(f"  [{i+1:>2}/{args.n}] {ms:7.1f} ms")
        except Exception as exc:
            failures += 1
            print(f"  [{i+1:>2}/{args.n}] FAILED -- {type(exc).__name__}: {exc!r}")
        # small sleep so the backend isn't slammed
        await asyncio.sleep(0.4)

    if not samples_ms:
        print("no successful samples — backend down or no alerts firing")
        return 1

    sorted_ms = sorted(samples_ms)
    def pct(p: float) -> float:
        idx = min(len(sorted_ms) - 1, int(round((p / 100) * (len(sorted_ms) - 1))))
        return sorted_ms[idx]

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "image": str(args.image),
        "n": len(samples_ms),
        "failures": failures,
        "p50_ms": round(statistics.median(samples_ms), 1),
        "p95_ms": round(pct(95), 1),
        "p99_ms": round(pct(99), 1),
        "max_ms": round(max(samples_ms), 1),
        "min_ms": round(min(samples_ms), 1),
        "mean_ms": round(statistics.fmean(samples_ms), 1),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2))
    print(f"\n[latency] wrote {OUT}")
    print(f"[latency] n={summary['n']}  p50 {summary['p50_ms']}ms  p95 {summary['p95_ms']}ms  p99 {summary['p99_ms']}ms  max {summary['max_ms']}ms")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--ws", default="ws://127.0.0.1:8000/ws/live")
    ap.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
