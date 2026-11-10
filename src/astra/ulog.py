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
          "sensor_combined", "vehicle_attitude", "logged_messages"]


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
    lm = by.get("logged_messages")
    if lm is not None:
        txt = ["".join(chr(int(c)) for c in row if int(c) != 0) for row in
               np.stack([lm[k] for k in sorted((k for k in lm if k.startswith("message[")),
                                               key=lambda s: int(s[8:-1]))], axis=1)]
        fl.messages = list(zip((lm["timestamp"] / 1e6).tolist(), txt))
    return fl
