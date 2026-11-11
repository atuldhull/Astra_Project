"""A6 parameter advisor: measured trade-off of candidate EKF changes on the vendor's own params.

    astra advise --params vendor.parm --out runs/advise [--nbenign 20] [--parallel 4]

For every candidate setting (overlaid on the vendor file), flies the same benign flights (cost:
nav alerts, failsafes, mission failures) and the same slow drag-off attacks (benefit: stock
autopilot detection during the attack). Never recommends a change on its own; it prints the
table and flags the settings with zero benign cost. Small benign samples are labelled as such.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

from astra.batch import run_batch
from astra.packs import PACKS

CANDIDATES: dict[str, dict] = {
    "vendor-as-is": {},
    "tight-gates": {"EK3_POS_I_GATE": 300, "EK3_VEL_I_GATE": 300},
    "tighter-gates": {"EK3_POS_I_GATE": 200, "EK3_VEL_I_GATE": 200},
    "low-noise": {"EK3_POSNE_M_NSE": 0.2, "EK3_VELNE_M_NSE": 0.1},
    "tight+low-noise": {"EK3_POS_I_GATE": 300, "EK3_VEL_I_GATE": 300, "EK3_POSNE_M_NSE": 0.2,
                        "EK3_VELNE_M_NSE": 0.1, "EK3_GLITCH_RAD": 10},
}

# PX4 EKF2 equivalents (defaults: P_NOISE 0.5 m, V_NOISE 0.3 m/s, gates 5 sigma)
CANDIDATES_PX4: dict[str, dict] = {
    "vendor-as-is": {},
    "tight-gates": {"EKF2_GPS_P_GATE": 3.0, "EKF2_GPS_V_GATE": 3.0},
    "low-noise": {"EKF2_GPS_P_NOISE": 0.3, "EKF2_GPS_V_NOISE": 0.15},
    "tight+low-noise": {"EKF2_GPS_P_GATE": 3.0, "EKF2_GPS_V_GATE": 3.0, "EKF2_GPS_P_NOISE": 0.3,
                        "EKF2_GPS_V_NOISE": 0.15},
}


def _merge(vendor: Path | None, overlay: dict, out: Path) -> Path:
    from astra.sitl import read_params  # reads ArduPilot, Mission Planner and QGC formats

    params = read_params(vendor) if vendor else {}
    params.update(overlay)
    fmt = lambda v: str(int(v)) if float(v).is_integer() else str(v)  # noqa: E731
    out.write_text("".join(f"{k} {fmt(v)}\n" for k, v in params.items()))
    return out


def _with_gps(scs, profile: str | None):
    if not profile:
        return scs
    return [s.model_copy(update={"sensors": s.sensors.model_copy(update={"gps": profile})}) for s in scs]


def advise(vendor: Path | None, out: Path, nbenign: int = 20, parallel: int = 4,
           autopilot: str = "ardupilot", gps_profile: str | None = None) -> list[dict]:
    """gps_profile: override the benign flights' GNSS noise model ("harsh" = noisier real receivers),
    so the benign cost isn't measured on unrealistically clean GPS."""
    out.mkdir(parents=True, exist_ok=True)
    benign = _with_gps(PACKS["benign-v2"]()[:nbenign], gps_profile)
    atk = [s for s in PACKS["attack-test"]() if ("-g0-" in s.id or "-g1-" in s.id)
           and s.id.split("-")[-3] in ("r0.5", "r1")]
    cands = CANDIDATES_PX4 if autopilot == "px4" else CANDIDATES
    speed = 10 if autopilot == "px4" else 20
    rows = []
    for name, overlay in cands.items():
        pf = _merge(vendor, overlay, out / f"{name}.parm")
        rb = run_batch([(s, 0) for s in benign], out / name / "benign", parallel=parallel, speedup=speed,
                       vendor_param_file=pf, autopilot=autopilot)["results"]
        ra = run_batch([(s, 0) for s in atk], out / name / "attack", parallel=parallel, speedup=speed,
                       vendor_param_file=pf, autopilot=autopilot)["results"]
        ob = [r for r in rb if r.outcome != "error"]
        oa = [r for r in ra if r.outcome != "error"]
        det = collections.Counter()
        for r in oa:
            kind = "consistent" if r.scenario_id.endswith("-c") else "naive"
            det[kind, "n"] += 1
            det[kind, "hit"] += bool(r.windows and r.windows[0].get("l0_detected_during"))
        rows.append({
            "setting": name, "overlay": overlay, "benign_runs": len(ob),
            "benign_failed": sum(r.outcome != "success" for r in ob),
            "benign_nav_alert": sum(bool(r.alerts) for r in ob),
            "naive": f"{det['naive', 'hit']}/{det['naive', 'n']}",
            "consistent": f"{det['consistent', 'hit']}/{det['consistent', 'n']}",
            "errors": (len(rb) - len(ob)) + (len(ra) - len(oa)),
        })
    (out / "advice.json").write_text(json.dumps(rows, indent=1))
    return rows


def render(rows: list[dict], nbenign: int) -> str:
    lines = ["| setting | overlay | benign failed | benign nav alerts | stock detects naive | stock detects consistent | errors |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['setting']} | `{r['overlay'] or 'none'}` | {r['benign_failed']}/{r['benign_runs']} | "
                     f"{r['benign_nav_alert']} | {r['naive']} | {r['consistent']} | {r['errors']} |")
    zero_cost = [r["setting"] for r in rows if r["benign_failed"] == 0 and r["benign_nav_alert"] == 0]
    lines.append(f"\nZero observed benign cost: {', '.join(zero_cost) or 'none'}.")
    if nbenign < 80:
        lines.append(f"Benign sample is {nbenign} flights: costs are indicative only. Re-run with --nbenign 80 "
                     "before changing a fielded airframe.")
    lines.append("Consistent (velocity-matched) spoofing is not fixable by EKF tuning; it needs a witness sensor "
                 "(see docs/v4/05-DETECTION-PHYSICS.md).")
    return "\n".join(lines)
