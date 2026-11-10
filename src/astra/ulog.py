"""PX4 ULog (.ulg) → astra.logs.FlightLog adapter (pyulog, BSD-3).

Maps the PX4 topics ASTRA's GPS/IMU channels need onto the ArduPilot-style series names used
everywhere else, so features/monitor/forensics run unchanged:

  GPS  ← sensor_gps | vehicle_gps_position  (fix, sats, lat/lon/alt, NED velocity → Spd/GCrs/VZ)
  GPA  ← same topic (eph → HAcc, epv → VAcc, s_variance_m_s → SAcc)
  POS  ← vehicle_global_position (lat/lon/alt) + vehicle_local_position (-z → RelHomeAlt)
  IMU  ← sensor_combined (accelerometer_m_s2, body FRD)
  ATT  ← vehicle_attitude (quaternion → roll/pitch/yaw, deg)
  MSG  ← logged_messages

Optical flow / rangefinder are not mapped yet (rare in public logs). Real logs have no SIM/ASTK,
so ground-truth evaluation is unavailable: these are for false-alarm and forensics use only.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from astra.logs import FlightLog

TOPICS = ["sensor_gps", "vehicle_gps_position", "vehicle_global_position", "vehicle_local_position",
          "sensor_combined", "vehicle_attitude", "logged_messages", "vehicle_global_position_groundtruth",
          "vehicle_status", "estimator_innovation_test_ratios"]

# ASTRA PX4 attack model numbers (sim/px4 patch) -> astra.evaluate CODE_NAMES codes
PX4_MODEL_TO_CODE = {1: 1, 2: 2, 3: 5, 4: 6, 6: 4}


def _quat_to_euler_deg(q0, q1, q2, q3):
    roll = np.degrees(np.arctan2(2 * (q0 * q1 + q2 * q3), 1 - 2 * (q1 * q1 + q2 * q2)))
    pitch = np.degrees(np.arcsin(np.clip(2 * (q0 * q2 - q3 * q1), -1, 1)))
    yaw = np.degrees(np.arctan2(2 * (q0 * q3 + q1 * q2), 1 - 2 * (q2 * q2 + q3 * q3))) % 360
    return roll, pitch, yaw


def load_ulog(path: str | Path) -> FlightLog:
    from pyulog import ULog

    u = ULog(str(path), TOPICS)
    by, inst = {}, {}
    for d in u.data_list:  # prefer instance 0, fall back to the lowest instance present
        if d.name not in by or d.multi_id < inst[d.name]:
            by[d.name], inst[d.name] = d.data, d.multi_id
    fl = FlightLog(str(path))
    gps = by.get("sensor_gps") or by.get("vehicle_gps_position")
    if gps is None:
        raise ValueError("raw GPS not logged in this ULog (sensor_gps / vehicle_gps_position missing; check the logging profile, SDLOG_PROFILE)")

    def lat_lon_alt(g):
        if "latitude_deg" in g:
            return g["latitude_deg"], g["longitude_deg"], g.get("altitude_msl_m", np.zeros(len(g["timestamp"])))
        return g["lat"] / 1e7, g["lon"] / 1e7, g["alt"] / 1e3

    t = gps["timestamp"] / 1e6
    la, lo, al = lat_lon_alt(gps)
    vn, ve, vd = gps["vel_n_m_s"], gps["vel_e_m_s"], gps["vel_d_m_s"]
    fl.series["GPS"] = {"t": t, "Status": gps["fix_type"].astype(float), "NSats": gps["satellites_used"].astype(float),
                        "HDop": gps.get("hdop", np.full(len(t), np.nan)), "Lat": la, "Lng": lo, "Alt": al,
                        "Spd": np.hypot(vn, ve), "GCrs": np.degrees(np.arctan2(ve, vn)) % 360, "VZ": vd}
    fl.series["GPA"] = {"t": t, "HAcc": gps["eph"], "VAcc": gps["epv"],
                        "SAcc": gps.get("s_variance_m_s", np.full(len(t), np.nan))}
    gp, lp = by.get("vehicle_global_position"), by.get("vehicle_local_position")
    if gp is None or lp is None:
        raise ValueError("no estimator position topics")
    gt = gp["timestamp"] / 1e6
    glat = gp["lat"] if gp["lat"].dtype.kind == "f" else gp["lat"] / 1e7
    glon = gp["lon"] if gp["lon"].dtype.kind == "f" else gp["lon"] / 1e7
    rel = np.interp(gt, lp["timestamp"] / 1e6, -lp["z"])
    fl.series["POS"] = {"t": gt, "Lat": glat, "Lng": glon, "Alt": gp["alt"], "RelHomeAlt": rel - np.nanmin(rel[:50])}
    sc = by["sensor_combined"]
    fl.series["IMU"] = {"t": sc["timestamp"] / 1e6, "I": np.zeros(len(sc["timestamp"])),
                        "AccX": sc["accelerometer_m_s2[0]"], "AccY": sc["accelerometer_m_s2[1]"],
                        "AccZ": sc["accelerometer_m_s2[2]"]}
    at = by["vehicle_attitude"]
    r, p, y = _quat_to_euler_deg(at["q[0]"], at["q[1]"], at["q[2]"], at["q[3]"])
    fl.series["ATT"] = {"t": at["timestamp"] / 1e6, "Roll": r, "Pitch": p, "Yaw": y}
    # ── ASTRA SITL extras: simulator truth and the attack window rebuilt from logged params ──
    gtp = by.get("vehicle_global_position_groundtruth")
    if gtp is not None:
        glat2 = gtp["lat"] if gtp["lat"].dtype.kind == "f" else gtp["lat"] / 1e7
        glon2 = gtp["lon"] if gtp["lon"].dtype.kind == "f" else gtp["lon"] / 1e7
        fl.series["SIM"] = {"t": gtp["timestamp"] / 1e6, "Lat": glat2, "Lng": glon2, "Alt": gtp["alt"]}
    params = dict(u.initial_parameters)
    for _t, name, val in u.changed_parameters:
        params[name] = val
    fl.params = {k: float(v) for k, v in params.items()}
    model = int(params.get("ASTRA_ATK_MODEL", 0) or 0)
    vs = by.get("vehicle_status")
    if model and vs is not None:
        armed = np.nonzero(vs["arming_state"] == 2)[0]
        if len(armed):
            t_arm = vs["timestamp"][armed[0]] / 1e6
            s0 = t_arm + float(params.get("ASTRA_ATK_ARM_S", 0.0))
            s1 = s0 + float(params.get("ASTRA_ATK_DUR", 0.0))
            tt = np.arange(t[0], t[-1], 0.05)
            act = ((tt >= s0) & (tt < s1)).astype(float)
            z = np.zeros(len(tt))
            fl.series["ASTK"] = {"t": tt, "Act": act, "Code": act * PX4_MODEL_TO_CODE.get(model, model),
                                 "OfsN": z, "OfsE": z, "VbN": z, "VbE": z, "En": 1 - act * (model in (1, 2)), "Jam": z}
    # EKF2 GPS innovation test ratios (>1 = rejected) mapped onto ArduPilot's XKF4 names, so the
    # shared "did the stock autopilot notice?" evaluation works for PX4 too.
    itr = by.get("estimator_innovation_test_ratios")
    if itr is not None:
        def _mx(prefix):
            cols = [v for k, v in itr.items() if k.startswith(prefix)]
            return np.max(np.stack(cols), axis=0) if cols else np.zeros(len(itr["timestamp"]))
        fl.series["XKF4"] = {"t": itr["timestamp"] / 1e6, "C": np.zeros(len(itr["timestamp"])),
                             "SV": _mx("gps_hvel"), "SP": _mx("gps_hpos"), "SH": _mx("gps_vpos"),
                             "SM": np.zeros(len(itr["timestamp"])), "FS": np.zeros(len(itr["timestamp"])),
                             "TS": np.zeros(len(itr["timestamp"])), "SS": np.zeros(len(itr["timestamp"])),
                             "GPS": np.zeros(len(itr["timestamp"]))}
    elif "SIM" in fl.series:
        z = np.zeros(2)
        fl.series["XKF4"] = {"t": np.array([t[0], t[-1]]), **{k: z for k in ("C", "SV", "SP", "SH", "SM", "FS", "TS", "SS", "GPS")}}
    # PX4 text messages live in the ULog message section, not in a data topic.
    import re
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    fl.messages = [(m.timestamp / 1e6, ansi.sub("", m.message).strip()) for m in u.logged_messages]
    return fl
