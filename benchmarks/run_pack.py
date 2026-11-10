"""Run a built-in pack and write results + a summary table.

usage: python benchmarks/run_pack.py PACK OUT_DIR [--seeds N] [--parallel P] [--speedup S] [--only SUBSTR]
"""
import argparse, json, sys, time
from pathlib import Path
from astra.batch import run_batch
from astra.packs import PACKS

ap = argparse.ArgumentParser()
ap.add_argument("pack"); ap.add_argument("out")
ap.add_argument("--seeds", type=int, default=3); ap.add_argument("--parallel", type=int, default=4)
ap.add_argument("--speedup", type=int, default=10); ap.add_argument("--only", default="")
ap.add_argument("--keep-logs", action="store_true")
ap.add_argument("--autopilot", default="ardupilot", choices=["ardupilot", "px4"])
a = ap.parse_args()
scs = [s for s in PACKS[a.pack]() if a.only in s.id]
jobs = [(s, k) for s in scs for k in range(a.seeds)]
print(f"{len(jobs)} runs, parallel={a.parallel}, speedup={a.speedup}", flush=True)
done = [0]
def tick(r):
    done[0] += 1
    w = r.windows[0] if r.windows else {}
    print(f"[{done[0]}/{len(jobs)}] {r.scenario_id} s{r.seed}: {r.outcome:10s} "
          f"maxerr={w.get('max_nav_error_m')} during={w.get('l0_detected_during')} lat={w.get('l0_detect_latency_s')} release_only={w.get('l0_release_only')} ({r.wall_s}s)", flush=True)
out = run_batch(jobs, Path(a.out), parallel=a.parallel, speedup=a.speedup, on_result=tick, keep_logs=a.keep_logs,
                autopilot=a.autopilot)
print(json.dumps(out["summary"]))
