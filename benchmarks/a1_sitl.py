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
DIMS2 = [Dim("rate", 0.1, 3.0), Dim("ramp", 0.0, 90.0)]
DIMS4 = DIMS2 + [Dim("bearing", 0.0, 359.0), Dim("delay", 5.0, 60.0)]
DIMS = DIMS2


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
    ap.add_argument("--dims", type=int, default=2, choices=[2, 4])
    ap.add_argument("--ntest", type=int, default=200, help="4-D only: Sobol ground-truth points")
    a = ap.parse_args()
    global DIMS
    DIMS = DIMS4 if a.dims == 4 else DIMS2
    out = Path(a.out)
    cal = monitor.Calibration(**json.loads(Path(a.cal).read_text())[a.cfg]) if a.cal else None

    def ev(sub):
        return SitlEvaluator(base_scenario(), out / sub, detector=a.detector, a2_cal=cal, parallel=a.parallel)

    if a.dims == 4:
        from scipy.stats import qmc
        U_grid = qmc.Sobol(4, scramble=True, seed=1234).random(a.ntest)
    else:
        gx, gy = (int(v) for v in a.grid.split("x"))
        U_grid = np.array([[i / (gx - 1), j / (gy - 1)] for i in range(gx) for j in range(gy)])
    e_grid = ev("grid")
    y_grid = np.array(e_grid([{d.name: float(d.scale(u[k])) for k, d in enumerate(DIMS)} for u in U_grid]))

    e_f = ev("fbm")
    f = FBM(DIMS, e_f, batch=a.parallel, n_init=12, seed=0).run(a.budget)
    e_r = ev("random")
    r = random_baseline(DIMS, e_r, a.budget, seed=0)

    def scores(h: History):
        U, y = h.arrays()
        p = predict(_fit(U, y, 0), U_grid, bool(y.mean() > 0.5)) > 0.5
        tp, tn = int((p & y_grid).sum()), int((~p & ~y_grid).sum())
        fp, fn = int((p & ~y_grid).sum()), int((~p & y_grid).sum())
        bal = 0.5 * (tp / max(1, tp + fn) + tn / max(1, tn + fp))
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        return {"accuracy": round(float((p == y_grid).mean()), 4), "balanced_accuracy": round(bal, 4),
                "f1_failure": round(f1, 4), "failures_found_in_budget": int(y.sum())}

    def acc(h: History):
        return scores(h)["accuracy"]

    res = {
        "detector": a.detector, "budget": a.budget, "grid": a.grid,
        "grid_stealthy_failure_fraction": float(y_grid.mean()),
        "fbm_grid_accuracy": acc(f.hist), "random_grid_accuracy": acc(r),
        "fbm_scores": scores(f.hist), "random_scores": scores(r),
        "fbm_undetected_rate_range_at_ramp": {str(rp): failure_extent(f.model(), DIMS, "rate", {"ramp": rp})
                                    for rp in (0, 30, 60, 90)} if a.dims == 2 else None,
        "grid": [{**{d.name: round(float(d.scale(u[k])), 3) for k, d in enumerate(DIMS)},
                  "stealthy_failure": bool(y)} for u, y in zip(U_grid, y_grid)],
        "fbm_log": e_f.log, "random_log": e_r.log,
    }
    (out / "a1_result.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k not in ("grid", "fbm_log", "random_log")}, indent=1))


if __name__ == "__main__":
    main()
