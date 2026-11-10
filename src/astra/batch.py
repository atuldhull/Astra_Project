"""Run many (scenario, seed) jobs in parallel with bounded resources.

Default concurrency is deliberately conservative (thermal budget on a laptop):
min(4, cpu_count // 4). Override with ASTRA_MAX_PARALLEL.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterable

from astra.runner import RunResult, fly
from astra.scenario import Scenario


def default_parallel() -> int:
    env = os.environ.get("ASTRA_MAX_PARALLEL")
    if env:
        return max(1, int(env))
    return max(1, min(4, (os.cpu_count() or 4) // 4))


def run_batch(jobs: Iterable[tuple[Scenario, int]], out_dir: Path, *, parallel: int | None = None,
              speedup: int = 5, vendor_param_file: Path | None = None, cpus: float = 1.5,
              on_result: Callable[[RunResult], None] | None = None, keep_logs: bool = False,
              extra_scripts: dict[str, str] | None = None, autopilot: str = "ardupilot") -> dict:
    jobs = list(jobs)
    parallel = parallel or default_parallel()
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    results: list[RunResult] = []
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        if autopilot == "px4":
            from astra.runner_px4 import fly_px4
            futs = {ex.submit(fly_px4, sc, seed, out_dir / f"{sc.id}__s{seed}", speedup=speedup,
                              vendor_param_file=vendor_param_file): (sc.id, seed) for sc, seed in jobs}
        else:
            futs = {
                ex.submit(fly, sc, seed, out_dir / f"{sc.id}__s{seed}", speedup=speedup,
                          vendor_param_file=vendor_param_file, cpus=cpus, keep_logs=keep_logs,
                          extra_scripts=extra_scripts): (sc.id, seed)
                for sc, seed in jobs
            }
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            if on_result:
                on_result(r)
    wall = time.monotonic() - t0
    sim_total = sum(r.metrics.get("sim_duration_s") or 0 for r in results)
    summary = {
        "jobs": len(results),
        "parallel": parallel,
        "speedup": speedup,
        "wall_s": round(wall, 1),
        "sim_flight_s": round(sim_total, 1),
        "aggregate_realtime_factor": round(sim_total / wall, 2) if wall else None,
        "errors": sum(r.outcome == "error" for r in results),
        "autopilot": autopilot,
    }
    with (out_dir / "results.jsonl").open("w") as f:
        for r in sorted(results, key=lambda r: (r.scenario_id, r.seed)):
            f.write(json.dumps(asdict(r)) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return {"summary": summary, "results": results}
