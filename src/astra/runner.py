"""Fly one scenario seed in SITL and record what happened.

Procedure (no vendor flight parameter is changed):
  1. boot SITL with vendor params + harness params + Lua attack script
  2. wait until the vehicle reports it is ready to arm
  3. upload the mission, GUIDED takeoff, then AUTO
  4. sample true position (SIMSTATE, from the simulator) and believed
     position (GLOBAL_POSITION_INT, from the EKF) until the run ends
  5. classify the outcome and compute metrics

Time is always simulator time (time_boot_ms), never wall-clock, so results
don't depend on host load or speed-up.
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pymavlink import mavutil

from astra.attacks import lua_script
from astra.geo import latlon_to_ne, ne_to_latlon
from astra.scenario import Scenario
from astra.sitl import Sitl, SitlConfig

ML = mavutil.mavlink

ALERT_WORDS = (
    "gps glitch", "ekf variance", "ekf failsafe", "gps lost", "position lost",
    "vibration", "ekf3 lane switch", "bad gps", "ekf primary changed",
    "failsafe", "gps unhealthy",
)


@dataclass
class Sample:
    t: float  # sim seconds since boot
    true_n: float
    true_e: float
    alt_rel: float  # EKF relative altitude (belief); horizontal attacks leave it intact
    est_n: float | None
    est_e: float | None
    mode: str
    armed: bool
    nav_idx: int


@dataclass
class RunResult:
    scenario_id: str
    scenario_sha256: str
    seed: int
    outcome: str
    passed: bool
    reason: str
    metrics: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list)  # [sim_t, text] navigation-health alerts
    texts: list = field(default_factory=list)  # [sim_t, text] every STATUSTEXT (debug/audit)
    modes: list = field(default_factory=list)  # [sim_t, mode]
    perturbation: dict = field(default_factory=dict)
    log_files: list = field(default_factory=list)
    windows: list = field(default_factory=list)  # per-attack ground-truth evaluation (astra.evaluate)
    wall_s: float = 0.0


def seed_perturbation(sc: Scenario, seed: int) -> dict:
    """Deterministic per-seed nuisance variation (wind), so seeds explore conditions, not noise."""
    rng = random.Random(f"{sc.content_hash()}:{seed}")
    env = sc.environment
    p = {
        "SIM_WIND_SPD": max(0.0, round(env.wind_speed_ms + rng.uniform(-1.0, 1.0), 3)),
        "SIM_WIND_DIR": round((env.wind_dir_deg + rng.uniform(-20, 20)) % 360, 2),
        "SIM_WIND_TURB": max(0.0, round(env.wind_turbulence + rng.uniform(0, 0.5), 3)),
    }
    if sc.sensors.imu == "mems":
        # Consumer-MEMS-like after factory/user calibration (order-of-magnitude, documented in
        # docs/v4/PROGRESS.md): residual accel bias ~0.05 m/s^2 (1 sigma) per axis, gyro bias
        # ~0.1 deg/s, motor-vibration noise on. The EKF still has to estimate these biases, which is
        # exactly what lets a slow spoof hide inside them.
        for ax in "XYZ":
            p[f"SIM_ACC1_BIAS_{ax}"] = round(rng.gauss(0, 0.05), 4)
            p[f"SIM_ACC2_BIAS_{ax}"] = round(rng.gauss(0, 0.05), 4)
            p[f"SIM_GYR1_BIAS_{ax}"] = round(rng.gauss(0, 0.0017), 5)
            p[f"SIM_GYR2_BIAS_{ax}"] = round(rng.gauss(0, 0.0017), 5)
        p["SIM_ACC1_RND"] = 0.5
        p["SIM_ACC2_RND"] = 0.5
        p["SIM_GYR1_RND"] = 0.05
        p["SIM_GYR2_RND"] = 0.05
    if sc.sensors.gps == "typical":
        # Single-frequency GNSS, open sky: ~1 m (1-sigma) slowly wandering position error,
        # 30-90 s correlation, 0.05-0.12 m/s velocity noise. Reported accuracy matches.
        pos = round(rng.uniform(0.7, 1.5), 3)
        p.update({"SIM_GPS1_PNSE": pos, "SIM_GPS1_PTAU": round(rng.uniform(30, 90), 1),
                  "SIM_GPS1_VNSE": round(rng.uniform(0.05, 0.12), 3),
                  "SIM_GPS1_NSEED": rng.randint(1, 2**31 - 1),
                  "SIM_GPS1_ACC": round(1.5 * pos, 2)})
    return p


def sensor_params(sc: Scenario) -> dict:
    """Passive extra sensors: present and logged, NOT selected as EKF sources (EK3_SRC* untouched)."""
    p: dict = {}
    if sc.sensors.optical_flow:
        p.update({"SIM_FLOW_ENABLE": 1, "FLOW_TYPE": 10, "SIM_FLOW_RND": 0.05})
    if sc.sensors.rangefinder or sc.sensors.optical_flow:
        p.update({"RNGFND1_TYPE": 100, "RNGFND1_MIN": 0.2, "RNGFND1_MAX": 100,
                  "RNGFND1_ORIENT": 25, "SIM_SONAR_SCALE": 10})
    return p


class _Flight:
    def __init__(self, mav, sc: Scenario):
        self.m = mav
        self.sc = sc
        self.t = 0.0
        self.mode = "UNKNOWN"
        self.armed = False
        self.nav_idx = 0
        self.true = None  # (lat, lon, alt_amsl)
        self.est = None
        self.alerts: list = []
        self.texts: list = []
        self.modes: list = []
        self.samples: list[Sample] = []
        self.landed_state = 0
        self._last_sample_t = -1.0
        self.landed_on_ground = False

    # ── message pump ────────────────────────────────────────────────────
    def pump(self, timeout=1.0):
        msg = self.m.recv_match(blocking=True, timeout=timeout)
        if msg is None:
            return None
        typ = msg.get_type()
        if hasattr(msg, "time_boot_ms"):
            self.t = msg.time_boot_ms / 1000.0
        if typ == "HEARTBEAT" and msg.get_srcComponent() == 1 and msg.type != ML.MAV_TYPE_GCS:
            mode = mavutil.mode_string_v10(msg)
            armed = bool(msg.base_mode & ML.MAV_MODE_FLAG_SAFETY_ARMED)
            if mode != self.mode:
                self.modes.append([round(self.t, 2), mode])
            self.mode, self.armed = mode, armed
        elif typ == "SIMSTATE":
            self.true = (msg.lat / 1e7, msg.lng / 1e7, None)
        elif typ == "GLOBAL_POSITION_INT":
            self.est = (msg.lat / 1e7, msg.lon / 1e7, msg.relative_alt / 1000.0)
            self._maybe_sample()
        elif typ == "AHRS2":  # simulator ground-truth altitude is not in SIMSTATE; use AHRS2 as fallback
            pass
        elif typ == "MISSION_CURRENT":
            self.nav_idx = msg.seq
        elif typ == "EXTENDED_SYS_STATE":
            self.landed_state = msg.landed_state
        elif typ == "STATUSTEXT":
            txt = msg.text.strip()
            self.texts.append([round(self.t, 2), txt])
            if any(w in txt.lower() for w in ALERT_WORDS):
                self.alerts.append([round(self.t, 2), txt])
        return msg

    def _maybe_sample(self):
        if self.true is None or self.t - self._last_sample_t < 0.2:
            return
        self._last_sample_t = self.t
        h = self.sc.home
        tn, te = latlon_to_ne(h.lat, h.lon, self.true[0], self.true[1])
        en = ee = None
        if self.est is not None and (self.est[0] != 0 or self.est[1] != 0):
            en, ee = latlon_to_ne(h.lat, h.lon, self.est[0], self.est[1])
        alt = self.est[2] if self.est else 0.0
        self.samples.append(Sample(self.t, tn, te, alt, en, ee, self.mode, self.armed, self.nav_idx))

    def run_until(self, pred, sim_timeout_s, wall_timeout_s=600):
        t_end = self.t + sim_timeout_s
        w_end = time.monotonic() + wall_timeout_s
        while self.t < t_end and time.monotonic() < w_end:
            self.pump(0.5)
            if pred():
                return True
        return False

    # ── commands ────────────────────────────────────────────────────────
    def command(self, cmd, *p):
        p = list(p) + [0] * (7 - len(p))
        self.m.mav.command_long_send(1, 1, cmd, 0, *p)

    def set_mode(self, name):
        mode_id = self.m.mode_mapping()[name]
        self.m.mav.set_mode_send(1, ML.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id)
        return self.run_until(lambda: self.mode == name, 10)

    def request_streams(self):
        for msg_id, hz in ((ML.MAVLINK_MSG_ID_SIMSTATE, 10), (ML.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 10),
                           (ML.MAVLINK_MSG_ID_MISSION_CURRENT, 2), (ML.MAVLINK_MSG_ID_EXTENDED_SYS_STATE, 2)):
            self.command(ML.MAV_CMD_SET_MESSAGE_INTERVAL, msg_id, int(1e6 / hz))

    def upload_mission(self):
        sc, h = self.sc, self.sc.home
        items = [(ML.MAV_CMD_NAV_WAYPOINT, ML.MAV_FRAME_GLOBAL, h.lat, h.lon, 0.0)]
        items.append((ML.MAV_CMD_NAV_TAKEOFF, ML.MAV_FRAME_GLOBAL_RELATIVE_ALT, h.lat, h.lon,
                      sc.mission.takeoff_alt_m))
        for w in sc.mission.waypoints:
            lat, lon = ne_to_latlon(h.lat, h.lon, w.north_m, w.east_m)
            items.append((ML.MAV_CMD_NAV_WAYPOINT, ML.MAV_FRAME_GLOBAL_RELATIVE_ALT, lat, lon, w.alt_m))
        last = sc.mission.waypoints[-1]
        glat, glon = ne_to_latlon(h.lat, h.lon, last.north_m, last.east_m)
        end_cmd = {"land": ML.MAV_CMD_NAV_LAND, "rtl": ML.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                   "loiter": ML.MAV_CMD_NAV_LOITER_UNLIM}[sc.mission.end]
        items.append((end_cmd, ML.MAV_FRAME_GLOBAL_RELATIVE_ALT, glat, glon, 0.0))

        last_err = "timed out"
        for _attempt in range(5):
            self._wait_mission_ready()
            ok, last_err = self._upload_once(items)
            if ok:
                return len(items)
            self.run_until(lambda: False, 3)
        raise RuntimeError(f"mission upload failed after 5 attempts: {last_err}")

    def _wait_mission_ready(self, wall_timeout_s: float = 20) -> None:
        """The mission subsystem answers MISSION_REQUEST_LIST with MISSION_COUNT once it's ready."""
        deadline = time.monotonic() + wall_timeout_s
        while time.monotonic() < deadline:
            self.m.mav.mission_request_list_send(1, 1, ML.MAV_MISSION_TYPE_MISSION)
            if self.m.recv_match(type="MISSION_COUNT", blocking=True, timeout=2) is not None:
                self.m.mav.mission_ack_send(1, 1, ML.MAV_MISSION_ACCEPTED, ML.MAV_MISSION_TYPE_MISSION)
                return

    def _upload_once(self, items) -> tuple[bool, str]:
        self.m.mav.mission_count_send(1, 1, len(items), ML.MAV_MISSION_TYPE_MISSION)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            msg = self.m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"],
                                    blocking=True, timeout=2)
            if msg is None:
                continue
            if msg.get_type() == "MISSION_ACK":
                if msg.type == ML.MAV_MISSION_ACCEPTED:
                    return True, "ok"
                if msg.type == ML.MAV_MISSION_INVALID_SEQUENCE:
                    # ArduPilot sends this for a late duplicate item but keeps the transfer open.
                    continue
                return False, f"rejected: {msg.type}"
            seq = msg.seq
            if not 0 <= seq < len(items):
                continue
            cmd, frame, lat, lon, alt = items[seq]
            self.m.mav.mission_item_int_send(1, 1, seq, frame, cmd, 0, 1, 0, 0, 0, 0,
                                             int(lat * 1e7), int(lon * 1e7), alt,
                                             ML.MAV_MISSION_TYPE_MISSION)
        return False, "timed out"

    def wait_ready_and_arm(self, sim_timeout_s=120):
        """Retry arming in GUIDED until prearm checks (EKF, GPS) pass."""
        t_end = self.t + sim_timeout_s
        while self.t < t_end:
            if self.mode != "GUIDED":
                self.set_mode("GUIDED")
            self.command(ML.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            if self.run_until(lambda: self.armed, 3):
                return True
            self.run_until(lambda: False, 2)
        return False


def fly(sc: Scenario, seed: int, workdir: Path, *, speedup: int = 5,
        vendor_param_file: Path | None = None, cpus: float = 1.5, keep_logs: bool = False,
        extra_scripts: dict[str, str] | None = None) -> RunResult:
    wall0 = time.monotonic()
    pert = seed_perturbation(sc, seed)
    extra = {**pert, **sensor_params(sc)}
    extra["WPNAV_SPEED"] = sc.mission.speed_ms * 100  # mission cruise speed is a scenario property
    cfg = SitlConfig(
        home=(sc.home.lat, sc.home.lon, sc.home.alt_m, sc.home.heading_deg),
        workdir=workdir, speedup=speedup, extra_params=extra,
        vendor_param_file=vendor_param_file, lua_script=lua_script(sc), cpus=cpus,
        extra_scripts=dict(extra_scripts or {}),
    )
    res = RunResult(sc.id, sc.content_hash(), seed, "error", False, "", perturbation=pert)
    sitl = Sitl(cfg)
    try:
        mav = sitl.start()
        f = _Flight(mav, sc)
        f.request_streams()
        f.run_until(lambda: f.t > 15 and f.true is not None, 60, wall_timeout_s=90)  # let storage/EKF initialise
        n_items = f.upload_mission()
        if not f.wait_ready_and_arm():
            res.outcome, res.reason = "error", "vehicle never became ready to arm"
            return res
        t_arm = f.t
        f.command(ML.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, sc.mission.takeoff_alt_m)
        f.run_until(lambda: f.est is not None and f.est[2] >= 0.9 * sc.mission.takeoff_alt_m, 60)
        f.set_mode("AUTO")
        last_item = n_items - 1
        geofence = sc.expect.geofence_radius_m

        def ended():
            s = f.samples[-1] if f.samples else None
            if s and math.hypot(s.true_n, s.true_e) > geofence:
                return True
            if not f.armed and f.t - t_arm > 5:
                return True
            if sc.mission.end == "loiter" and f.nav_idx >= last_item and f.mode == "AUTO":
                return True
            # On the ground for 10 s after flying, even if still armed (a spoofed velocity can keep
            # the land detector from ever disarming the vehicle).
            if s and s.t - t_arm > 30 and len(f.samples) > 60:
                recent = [x for x in f.samples if x.t >= s.t - 10]
                if recent and recent[0].t <= s.t - 9.5 and all(x.alt_rel < 0.5 for x in recent):
                    f.landed_on_ground = True
                    return True
            return False

        finished = f.run_until(ended, sc.time_limit_s, wall_timeout_s=max(120, 3 * sc.time_limit_s / speedup))
        if sc.mission.end == "loiter" and finished:
            f.run_until(lambda: False, 10)  # let it settle in the loiter
        res.alerts, res.modes, res.texts = f.alerts, f.modes, f.texts
        _classify(res, f, sc, finished, t_arm)
    except Exception as exc:  # noqa: BLE001 - a broken run is a result, not a crash of the batch
        res.outcome, res.reason = "error", f"{type(exc).__name__}: {exc}"
    finally:
        sitl.stop()
        _post_process(res, sitl.logs(), workdir, keep_logs)
        res.wall_s = round(time.monotonic() - wall0, 2)
        (workdir / "result.json").write_text(json.dumps(asdict(res), indent=2))
    return res


def _classify(res: RunResult, f: _Flight, sc: Scenario, finished: bool, t_arm: float) -> None:
    gn, ge = sc.goal_offset()
    s = f.samples
    if not s:
        res.outcome, res.reason = "error", "no telemetry samples"
        return
    last = s[-1]
    true_goal = math.hypot(last.true_n - gn, last.true_e - ge)
    errs = [math.hypot(x.true_n - x.est_n, x.true_e - x.est_e) for x in s if x.est_n is not None]
    max_from_home = max(math.hypot(x.true_n, x.true_e) for x in s)
    est_goal = (math.hypot(last.est_n - gn, last.est_e - ge) if last.est_n is not None else None)
    m = res.metrics
    m.update(
        final_true_dist_to_goal_m=round(true_goal, 2),
        final_est_dist_to_goal_m=None if est_goal is None else round(est_goal, 2),
        max_nav_error_m=round(max(errs), 2) if errs else None,
        final_nav_error_m=round(errs[-1], 2) if errs else None,
        max_dist_from_home_m=round(max_from_home, 2),
        sim_duration_s=round(last.t - t_arm, 2),
        first_alert_t=f.alerts[0][0] - t_arm if f.alerts else None,
        n_alerts=len(f.alerts),
        final_mode=last.mode,
        stuck_armed_on_ground=bool(f.landed_on_ground and f.armed),
        goal_n_m=round(gn, 1),
        goal_e_m=round(ge, 1),
    )
    R = sc.expect.goal_radius_m
    aborted = any(md in ("LAND", "RTL", "ALT_HOLD", "BRAKE", "SMART_RTL") for _, md in f.modes[1:])
    if max_from_home > sc.expect.geofence_radius_m:
        outcome, why = "flyaway", f"left the {sc.expect.geofence_radius_m:.0f} m geofence"
    elif not finished:
        outcome, why = "timeout", "mission did not end within the time limit"
    elif true_goal <= R:
        outcome, why = "success", f"ended {true_goal:.1f} m from goal"
    elif est_goal is not None and est_goal <= R:
        outcome, why = "diverted", f"believed it reached the goal but was {true_goal:.0f} m away"
    elif aborted:
        outcome, why = "safe_abort", f"failsafe/abort, ended {true_goal:.0f} m from goal"
    else:
        outcome, why = "diverted", f"ended {true_goal:.0f} m from goal"
    res.outcome, res.reason = outcome, why
    res.passed = outcome in sc.expect.allowed_outcomes


def _post_process(res: RunResult, bins: list[Path], workdir: Path, keep_logs: bool) -> None:
    from astra import evaluate, logs

    if not bins:
        return
    try:
        fl = logs.load(bins[-1])
        logs.save_npz(fl, workdir / "flight.npz")
        res.windows = evaluate.evaluate_dicts(fl) if fl.is_sitl else []
    except Exception as exc:  # noqa: BLE001
        res.reason = (res.reason + f" | log post-process failed: {exc}").strip(" |")
    if keep_logs:
        res.log_files = [str(p) for p in bins]
    else:
        for p in bins:
            p.unlink(missing_ok=True)
        res.log_files = []
