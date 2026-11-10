"""A6 v1: can EKF parameter tuning alone close the slow drag-off gap? (stock autopilot detection)

For each parameter setting: fly benign flights (cost: nav alerts / failsafes / mission failures) and
slow drag-offs (benefit: stock detection during the attack). Same scenarios and seeds for every
setting, so differences are due to the parameters.

usage: python benchmarks/a6_params.py OUT_DIR [--parallel 6] [--nbenign 20]
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from astra.batch import run_batch
from astra.packs import PACKS

# ArduPilot 4.7 EKF3 defaults: POSNE_M_NSE 0.5, VELNE_M_NSE 0.3, POS_I_GATE 500, VEL_I_GATE 500, GLITCH_RAD 25
SETTINGS = {
    "default": {},
    "tight-gates": {"EK3_POS_I_GATE": 300, "EK3_VEL_I_GATE": 300},
    "tighter-gates": {"EK3_POS_I_GATE": 200, "EK3_VEL_I_GATE": 200},
    "low-noise": {"EK3_POSNE_M_NSE": 0.2, "EK3_VELNE_M_NSE": 0.1},
    "tight+low-noise": {"EK3_POS_I_GATE": 300, "EK3_VEL_I_GATE": 300, "EK3_POSNE_M_NSE": 0.2,
                        "EK3_VELNE_M_NSE": 0.1, "EK3_GLITCH_RAD": 10},
}


def scenarios(nbenign: int):
    benign = PACKS["benign-v2"]()[:nbenign]
    atk = [s for s in PACKS["attack-test"]() if "-g0-" in s.id or "-g1-" in s.id]
    atk = [s for s in atk if s.id.split("-")[-3] in ("r0.5", "r1")]  # the regime stock misses
    return benign, atk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--nbenign", type=int, default=20)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    benign, atk = scenarios(a.nbenign)
    rows = []
    for name, params in SETTINGS.items():
        pf = out / f"{name}.parm"
        pf.write_text("".join(f"{k} {v}\n" for k, v in params.items()) or "# ArduPilot defaults\n")
        rb = run_batch([(s, 0) for s in benign], out / name / "benign", parallel=a.parallel, speedup=20,
                       vendor_param_file=pf)["results"]
        ra = run_batch([(s, 0) for s in atk], out / name / "attack", parallel=a.parallel, speedup=20,
                       vendor_param_file=pf)["results"]
        ok_b = [r for r in rb if r.outcome != "error"]
        ok_a = [r for r in ra if r.outcome != "error"]
        det = collections.Counter()
        for r in ok_a:
            w = r.windows[0] if r.windows else {}
            kind = "consistent" if r.scenario_id.endswith("-c") else "naive"
            det[kind, "n"] += 1
            det[kind, "hit"] += bool(w.get("l0_detected_during"))
        rows.append({
            "setting": name, "params": params,
            "benign_runs": len(ok_b), "benign_success": sum(r.outcome == "success" for r in ok_b),
            "benign_with_nav_alert": sum(bool(r.alerts) for r in ok_b),
            "benign_failsafe": sum(any(m in ("LAND", "RTL", "ALT_HOLD") for _, m in r.modes[1:]) for r in ok_b),
            "naive_detected": f"{det['naive', 'hit']}/{det['naive', 'n']}",
            "consistent_detected": f"{det['consistent', 'hit']}/{det['consistent', 'n']}",
            "errors": (len(rb) - len(ok_b)) + (len(ra) - len(ok_a)),
        })
        print(json.dumps(rows[-1]), flush=True)
    lines = ["# A6 v1: EKF parameter tuning vs slow drag-off (stock autopilot)\n",
             f"Benign: first {a.nbenign} benign-v2 flights. Attacks: attack-test geometries g0–g1, drag 0.5 and 1 m/s, "
             "ramps 0/15/60 s, consistent and naive.\n",
             "| setting | params | benign success | benign with nav alert | benign failsafe | stock detects naive | stock detects consistent | errors |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['setting']} | `{r['params'] or 'defaults'}` | {r['benign_success']}/{r['benign_runs']} | "
                     f"{r['benign_with_nav_alert']} | {r['benign_failsafe']} | {r['naive_detected']} | "
                     f"{r['consistent_detected']} | {r['errors']} |")
    Path("benchmarks/a6-params-v1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
