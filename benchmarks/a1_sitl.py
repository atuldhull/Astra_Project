"""A1 on the real simulator: FBM vs random sampling at equal budget, scored against a flown grid.

Space: consistent drag-off rate [0.1, 3] m/s × ramp [0, 90] s on a fixed 2.5 km mission.
Label: stealthy failure (mission failed AND the chosen detector missed it during the attack).

usage: python benchmarks/a1_sitl.py OUT_DIR [--detector stock|a2] [--cal FILE --cfg gps+imu+flow]
                                    [--budget 30] [--grid 7x6] [--parallel 6]
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np

from astra.detect import monitor
from astra.packs import THAR
from astra.scenario import Scenario
from astra.search import FBM, Dim, History, _fit, failure_extent, predict, random_baseline
from astra.search_sitl import SitlEvaluator

warnings.filterwarnings("ignore")
DIMS = [Dim("rate", 0.1, 3.0), Dim("ramp", 0.0, 90.0)]


def base_scenario() -> Scenario:
    return Scenario.model_validate({
        "id": "a1-base", "title": "A1 base: 2.5 km leg", "home": THAR,
        "mission": {"takeoff_alt_m": 30, "speed_ms": 10, "end": "land",
                    "waypoints": [{"north_m": 2500, "east_m": 0, "alt_m": 30}]},
        "sensors": {"optical_flow": True, "rangefinder": True}, "time_limit_s": 900,
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--detector", default="stock")
    ap.add_argument("--cal"); ap.add_argument("--cfg", default="gps+imu+flow")
    ap.add_argument("--budget", type=int, default=30)
    ap.add_argument("--grid", default="7x6")
    ap.add_argument("--parallel", type=int, default=6)
    a = ap.parse_args()
    out = Path(a.out)
    cal = monitor.Calibration(**json.loads(Path(a.cal).read_text())[a.cfg]) if a.cal else None

    def ev(sub):
        return SitlEvaluator(base_scenario(), out / sub, detector=a.detector, a2_cal=cal, parallel=a.parallel)

    gx, gy = (int(v) for v in a.grid.split("x"))
    U_grid = np.array([[i / (gx - 1), j / (gy - 1)] for i in range(gx) for j in range(gy)])
    e_grid = ev("grid")
    y_grid = np.array(e_grid([{d.name: float(d.scale(u[k])) for k, d in enumerate(DIMS)} for u in U_grid]))

    e_f = ev("fbm")
    f = FBM(DIMS, e_f, batch=a.parallel, n_init=12, seed=0).run(a.budget)
    e_r = ev("random")
    r = random_baseline(DIMS, e_r, a.budget, seed=0)

    def acc(h: History):
        U, y = h.arrays()
        return float(((predict(_fit(U, y, 0), U_grid, bool(y.mean() > 0.5)) > 0.5) == y_grid).mean())

    res = {
        "detector": a.detector, "budget": a.budget, "grid": a.grid,
        "grid_stealthy_failure_fraction": float(y_grid.mean()),
        "fbm_grid_accuracy": acc(f.hist), "random_grid_accuracy": acc(r),
        "fbm_undetected_rate_range_at_ramp": {str(rp): failure_extent(f.model(), DIMS, "rate", {"ramp": rp})
                                    for rp in (0, 30, 60, 90)},
        "grid": [{"rate": round(float(DIMS[0].scale(u[0])), 3), "ramp": round(float(DIMS[1].scale(u[1])), 1),
                  "stealthy_failure": bool(y)} for u, y in zip(U_grid, y_grid)],
        "fbm_log": e_f.log, "random_log": e_r.log,
    }
    (out / "a1_result.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k not in ("grid", "fbm_log", "random_log")}, indent=1))


if __name__ == "__main__":
    main()
