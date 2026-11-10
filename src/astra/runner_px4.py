"""Fly one scenario seed in PX4 SITL (SIH) and score it from the ULog.

PX4 differences handled here:
  * all params (vendor + harness + attack) are set at boot via PX4_PARAM_<NAME> env vars
  * missions start at item 0 (no home item); the vehicle arms in MISSION mode and starts
  * ground truth comes from the ULog (vehicle_global_position_groundtruth) after the flight
  * the attack timeline runs inside the patched simulated GPS (seconds after arming)

Supported attack models on PX4 (sim/px4 patch v1): jam_denial, jam_intermittent, jam_degrade,
spoof_jump, spoof_drag. "at_waypoint" triggers are converted to seconds after arming using an
estimate of take-off time (recorded in the result as `px4_trigger_s`).
"""

from __future__ import annotations

import json
import math
import subprocess
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from pymavlink import mavutil

from astra.geo import latlon_to_ne, ne_to_latlon
from astra.runner import RunResult, seed_perturbation
from astra.scenario import (JamDegrade, JamDenial, JamIntermittent, Scenario, SpoofDrag, SpoofJump)
from astra.sitl import read_params

ML = mavutil.mavlink
import os
PX4_IMAGE = os.environ.get("ASTRA_PX4_IMAGE", "astra/px4-sitl:v1.17.0")
ROOTFS = "/src/px4/build/px4_sitl_default/rootfs"
ETC = "/src/px4/build/px4_sitl_default/etc"


def attack_params(sc: Scenario) -> tuple[dict, float | None]:
    if not sc.attacks:
        return {"ASTRA_ATK_MODEL": 0}, None
    if len(sc.attacks) > 1:
        raise ValueError("PX4 patch v1 supports one attack per scenario")
    a = sc.attacks[0]
    if a.start.after_arm_s is not None:
        t0 = a.start.after_arm_s + a.start.delay_s
    else:  # at_waypoint k: estimate take-off (MPC_TKO_SPEED ~1.5 m/s) + mission start latency
        t0 = sc.mission.takeoff_alt_m / 1.5 + 8.0 + a.start.delay_s
    p = {"ASTRA_ATK_ARM_S": round(t0, 2), "ASTRA_ATK_DUR": a.duration_s}
    if isinstance(a, JamDenial):
        p["ASTRA_ATK_MODEL"] = 1
    elif isinstance(a, JamIntermittent):
        p.update(ASTRA_ATK_MODEL=2, ASTRA_ATK_PER=a.period_s, ASTRA_ATK_DUTY=a.duty)
    elif isinstance(a, SpoofJump):
        p.update(ASTRA_ATK_MODEL=3, ASTRA_ATK_JN=a.north_m, ASTRA_ATK_JE=a.east_m)
    elif isinstance(a, SpoofDrag):
        p.update(ASTRA_ATK_MODEL=4, ASTRA_ATK_RATE=a.rate_ms, ASTRA_ATK_BRG=a.bearing_deg,
                 ASTRA_ATK_RAMP=a.ramp_s, ASTRA_ATK_CONS=1 if a.consistent else 0)
    elif isinstance(a, JamDegrade):
        p["ASTRA_ATK_MODEL"] = 6
    else:
        raise ValueError(f"attack model {a.model} not supported on PX4 yet")
    return p, t0


def _env(sc: Scenario, seed: int, speedup: int, vendor: Path | None) -> tuple[dict, float | None]:
    env = {"PX4_SIM_SPEED_FACTOR": str(speedup), "PX4_HOME_LAT": str(sc.home.lat),
           "PX4_HOME_LON": str(sc.home.lon), "PX4_HOME_ALT": str(sc.home.alt_m)}
    params: dict = {}
    if vendor:
        params.update(read_params(vendor))
    atk, t0 = attack_params(sc)
    params.update(atk)
    pert = seed_perturbation(sc, seed)  # reuse the per-seed GNSS realism draw
    if "SIM_GPS1_PNSE" in pert:
        params.update(ASTRA_GPS_PNSE=pert["SIM_GPS1_PNSE"], ASTRA_GPS_PTAU=pert["SIM_GPS1_PTAU"])
    params.update(MPC_XY_CRUISE=sc.mission.speed_ms, MIS_TAKEOFF_ALT=sc.mission.takeoff_alt_m,
                  COM_RCL_EXCEPT=4, NAV_RCL_ACT=0, NAV_DLL_ACT=0, COM_DISARM_LAND=2.0,
                  MAV_0_BROADCAST=1)
    for k, v in params.items():
        env[f"PX4_PARAM_{k}"] = str(v)
    return env, t0


def fly_px4(sc: Scenario, seed: int, workdir: Path, *, speedup: int = 10,
            vendor_param_file: Path | None = None, cpus: float = 2.0, companion: dict | None = None) -> RunResult:
    from astra import evaluate, logs
    from astra.ulog import load_ulog

    wall0 = time.monotonic()
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "log").mkdir(exist_ok=True)
    res = RunResult(sc.id, sc.content_hash(), seed, "error", False, "")
    name = f"astra-px4-{uuid.uuid4().hex[:10]}"
    try:
        env, t0 = _env(sc, seed, speedup, vendor_param_file)
    except ValueError as exc:
        res.reason = str(exc)
        return res
    res.perturbation = {"px4_trigger_s": t0}
    h = sc.home
    items = [[int(ML.MAV_CMD_NAV_TAKEOFF), h.lat, h.lon, sc.mission.takeoff_alt_m]]
    for w in sc.mission.waypoints:
        lat, lon = ne_to_latlon(h.lat, h.lon, w.north_m, w.east_m)
        items.append([int(ML.MAV_CMD_NAV_WAYPOINT), lat, lon, w.alt_m])
    last = sc.mission.waypoints[-1]
    glat, glon = ne_to_latlon(h.lat, h.lon, last.north_m, last.east_m)
    end_cmd = {"land": ML.MAV_CMD_NAV_LAND, "rtl": ML.MAV_CMD_NAV_RETURN_TO_LAUNCH,
               "loiter": ML.MAV_CMD_NAV_LOITER_UNLIM}[sc.mission.end]
    items.append([int(end_cmd), glat, glon, 0.0])
    (workdir / "mission.json").write_text(json.dumps(
        {"items": items, "wall_limit_s": max(120.0, 2.5 * sc.time_limit_s / speedup)}))
    ctl = Path(__file__).resolve().parents[2] / "sim" / "px4" / "px4_control.py"
    comp_cmd = ""
    if companion:  # ASTRA Shield-Companion on PX4's onboard MAVLink link (as on a real companion computer)
        (workdir / "shield_cal.json").write_text(json.dumps(companion["cal"]))
        wl = max(120.0, 2.5 * sc.time_limit_s / speedup)
        comp_cmd = ("(PYTHONPATH=/astra_src timeout " + str(int(wl + 60)) + " python3 -c \"import json; "
                    "from astra.companion import monitor; "
                    f"monitor('udpin:127.0.0.1:14540', json.load(open('/work/shield_cal.json')), wall_timeout_s={wl}, "
                    "status_file='/work/companion.json')\" "
                    "> /work/companion.out 2>&1 &) && ")
    cmd = ["docker", "run", "--rm", "--name", name, "--cpus", str(cpus), "--memory", "1g",
           "-v", f"{(workdir / 'log').resolve()}:{ROOTFS}/log", "-v", f"{workdir.resolve()}:/work",
           "-v", f"{ctl}:/astra/px4_control.py:ro",
           "-v", f"{Path(__file__).resolve().parent}:/astra_src/astra:ro"]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += ["--entrypoint", "bash", PX4_IMAGE, "-c",
            f"cd {ROOTFS} && (../bin/px4 -d ../etc > /work/px4.out 2>&1 &) && " + comp_cmd +
            "python3 /astra/px4_control.py /work/mission.json /work/control.json"
            + (" && sleep 3" if companion else "")]
    finished = False
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True,
                       timeout=max(300.0, 3.0 * sc.time_limit_s / speedup + 240))
        ctl_out = json.loads((workdir / "control.json").read_text())
        res.texts, res.modes = ctl_out["texts"], ctl_out["modes"]
        finished = ctl_out["finished"]
        if not ctl_out["ok"]:
            res.reason = "harness: " + str(ctl_out["error"])
            res.wall_s = round(time.monotonic() - wall0, 2)
            (workdir / "result.json").write_text(json.dumps(asdict(res), indent=2))
            return res  # harness failure: outcome stays "error"
    except Exception as exc:  # noqa: BLE001
        res.reason = f"harness: {type(exc).__name__}: {exc}"
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        res.wall_s = round(time.monotonic() - wall0, 2)
        return res
    ulgs = sorted((workdir / "log").rglob("*.ulg"))
    if not ulgs:
        res.reason = (res.reason + " | no ULog").strip(" |")
        res.wall_s = round(time.monotonic() - wall0, 2)
        return res
    if companion and (workdir / "companion.json").exists():
        res.perturbation["companion"] = json.loads((workdir / "companion.json").read_text())
    fl = load_ulog(ulgs[-1])
    logs.save_npz(fl, workdir / "flight.npz")
    _classify_px4(res, fl, sc, finished)
    try:
        res.windows = evaluate.evaluate_dicts(fl) if fl.is_sitl else []
    except Exception as exc:  # noqa: BLE001
        res.reason += f" | eval failed: {exc}"
    res.wall_s = round(time.monotonic() - wall0, 2)
    (workdir / "result.json").write_text(json.dumps(asdict(res), indent=2))
    return res


def _classify_px4(res: RunResult, fl, sc: Scenario, finished: bool) -> None:
    from astra.evaluate import nav_error_series
    if not fl.is_sitl:
        res.outcome, res.reason = "error", "ULog has no ground truth"
        return
    h = sc.home
    sim, pos = fl["SIM"], fl["POS"]
    tn, te = latlon_to_ne(h.lat, h.lon, sim["Lat"], sim["Lng"])
    bn, be = latlon_to_ne(h.lat, h.lon, pos["Lat"], pos["Lng"])
    gn, ge = sc.goal_offset()
    true_goal = math.hypot(tn[-1] - gn, te[-1] - ge)
    est_goal = math.hypot(bn[-1] - gn, be[-1] - ge)
    far = float(max(math.hypot(a, b) for a, b in zip(tn, te)))
    _, err = nav_error_series(fl)
    res.metrics = {"final_true_dist_to_goal_m": round(true_goal, 2), "final_est_dist_to_goal_m": round(est_goal, 2),
                   "max_nav_error_m": round(float(err.max()), 2), "max_dist_from_home_m": round(far, 2),
                   "goal_n_m": gn, "goal_e_m": ge, "autopilot": "px4",
                   "sim_duration_s": round(float(sim["t"][-1] - sim["t"][0]), 2)}
    R = sc.expect.goal_radius_m
    if far > sc.expect.geofence_radius_m:
        o, why = "flyaway", "left the geofence"
    elif not finished:
        o, why = "timeout", "mission did not end within the time limit"
    elif true_goal <= R:
        o, why = "success", f"ended {true_goal:.1f} m from goal"
    elif est_goal <= R:
        o, why = "diverted", f"believed it reached the goal but was {true_goal:.0f} m away"
    else:
        o, why = "safe_abort", f"ended {true_goal:.0f} m from goal without believing it had arrived"
    res.outcome, res.reason = o, (res.reason + " | " + why).strip(" |") if res.reason else why
    res.passed = o in sc.expect.allowed_outcomes
