"""SITL-backed evaluator for A1 (failure-boundary mapping).

A "stealthy failure" = the mission outcome is not allowed by the scenario's expectation AND the
chosen detector did not alarm during the attack:
  detector="stock" → the autopilot's own alerts / EKF test ratios (astra.evaluate, L0)
  detector="a2"    → the A2 monitor with a given calibration
"""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np

from astra.batch import run_batch
from astra.scenario import Scenario

_counter = itertools.count()


def drag_scenario(base: Scenario, p: dict, sid: str) -> Scenario:
    d = base.model_dump(mode="json")
    d["id"] = sid
    d["attacks"] = [{
        "model": "spoof_drag", "start": {"at_waypoint": 1, "delay_s": float(p.get("delay", 20.0))},
        "duration_s": 3600, "rate_ms": float(p["rate"]), "ramp_s": float(p.get("ramp", 0.0)),
        "bearing_deg": float(p.get("bearing", 90.0)) % 360, "consistent": bool(p.get("consistent", True)),
    }]
    return Scenario.model_validate(d)


class SitlEvaluator:
    def __init__(self, base: Scenario, out_dir: Path, *, detector: str = "stock", a2_cal=None,
                 parallel: int = 6, speedup: int = 20, vendor_param_file: Path | None = None, seed: int = 0):
        self.base, self.out, self.detector, self.cal = base, out_dir, detector, a2_cal
        self.parallel, self.speedup, self.vendor, self.seed = parallel, speedup, vendor_param_file, seed
        self.log: list[dict] = []

    def _detected_a2(self, workdir: Path) -> bool:
        from astra import logs
        from astra.detect import features, monitor
        fl = logs.load_npz(workdir / "flight.npz")
        wins = fl.attack_windows()
        if not wins:
            return False
        ch = features.compute(fl)
        if self.cal.flow_model:
            features.apply_flow(ch, self.cal.flow_model, self.cal.flow_nuisance)
        det, _ = monitor.run(ch, self.cal)
        return det.alarm and det.t_alarm >= wins[0][0]

    def __call__(self, params: list[dict]) -> list[bool]:
        scs = [drag_scenario(self.base, p, f"{self.base.id}-fbm{next(_counter):04d}") for p in params]
        res = run_batch([(s, self.seed) for s in scs], self.out, parallel=self.parallel, speedup=self.speedup,
                        vendor_param_file=self.vendor)
        by_id = {r.scenario_id: r for r in res["results"]}
        labels = []
        for s, p in zip(scs, params):
            r = by_id[s.id]
            if r.outcome == "error":
                labels.append(False)  # conservative: an errored run is not evidence of failure
                self.log.append({**p, "outcome": "error", "label": False})
                continue
            failed = not r.passed
            if self.detector == "a2":
                detected = self._detected_a2(self.out / f"{s.id}__s{self.seed}")
            else:
                detected = bool(r.windows and r.windows[0].get("l0_detected_during"))
            y = failed and not detected
            labels.append(y)
            self.log.append({**p, "outcome": r.outcome, "detected": detected, "label": y,
                             "final_err_m": r.metrics.get("final_true_dist_to_goal_m")})
        return labels
