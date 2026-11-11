"""ASTRA Shield-Companion: the Shield check as a companion-computer process (any MAVLink autopilot).

Runs on a Raspberry Pi / Jetson / mission computer next to the autopilot (ArduPilot *or* PX4),
listening to standard telemetry (GPS_RAW_INT, GLOBAL_POSITION_INT). Same arithmetic and calibration
format as the onboard Lua script (`astra shield calibrate` output works unchanged):

    r = (p_i − p_j0)/Δt − v_mid over a trailing 2 s window → 4 s block medians → CUSUM

    python -m astra.companion --connect udp:0.0.0.0:14551 --cal shield-cal.json [--on-alarm land]
"""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from dataclasses import dataclass, field

import numpy as np
from pymavlink import mavutil

from astra.onboard import BLOCK_S, K_DESIGN, SPAN_S

ML = mavutil.mavlink
M_PER_1E7 = 0.011131949079327357


@dataclass
class ShieldState:
    sigma_inv: np.ndarray
    k: float
    h: float
    hist: list = field(default_factory=list)  # (t, n, e, vn, ve)
    lat0: int | None = None
    lon0: int | None = None
    coslat: float = 1.0
    bn: list = field(default_factory=list)
    be: list = field(default_factory=list)
    bstart: float | None = None
    cusum: float = 0.0
    alarm_t: float | None = None
    alarm_boot_t: float | None = None  # autopilot time_boot (s) at the alarm
    blocks: list = field(default_factory=list)  # (t, rn, re, q, S)

    def feed(self, t: float, lat_e7: int, lon_e7: int, vn: float, ve: float, airborne: bool) -> bool:
        """One GNSS fix. Returns True on the first alarm."""
        if self.lat0 is None:
            self.lat0, self.lon0 = lat_e7, lon_e7
            self.coslat = math.cos(math.radians(lat_e7 * 1e-7))
        n = (lat_e7 - self.lat0) * M_PER_1E7
        e = (lon_e7 - self.lon0) * M_PER_1E7 * self.coslat
        self.hist.append((t, n, e, vn, ve))
        while len(self.hist) > 2 and t - self.hist[0][0] > SPAN_S:
            self.hist.pop(0)
        if len(self.hist) < 3 or not airborne:
            self.bn, self.be, self.bstart = [], [], None
            return False
        a, b = self.hist[0], self.hist[-1]
        dt = b[0] - a[0]
        if dt < 0.5 * SPAN_S:
            return False
        mid = self.hist[(len(self.hist) + 1) // 2 - 1]
        self.bn.append((b[1] - a[1]) / dt - mid[3])
        self.be.append((b[2] - a[2]) / dt - mid[4])
        if self.bstart is None:
            self.bstart = t
        if t - self.bstart < BLOCK_S:
            return False
        rn, re = float(np.median(self.bn)), float(np.median(self.be))
        S = self.sigma_inv
        q = S[0, 0] * rn * rn + 2 * S[0, 1] * rn * re + S[1, 1] * re * re
        self.cusum = max(0.0, self.cusum + min(q, 100.0) - self.k)
        self.blocks.append((t, rn, re, q, self.cusum))
        self.bn, self.be, self.bstart = [], [], None
        if self.cusum > self.h and self.alarm_t is None:
            self.alarm_t = t
            return True
        return False


def monitor(conn: str, cal: dict, *, on_alarm: str = "alert", stop: threading.Event | None = None,
            log: list | None = None, wall_timeout_s: float = 1e9, status_file: str | None = None) -> ShieldState:
    st = ShieldState(np.asarray(cal["sigma_inv"]), float(cal.get("k", K_DESIGN)), float(cal["h"]))
    m = mavutil.mavlink_connection(conn, source_system=254, source_component=191)
    m.wait_heartbeat(timeout=60)
    for mid, hz in ((ML.MAVLINK_MSG_ID_GPS_RAW_INT, 5), (ML.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 5)):
        m.mav.command_long_send(m.target_system, m.target_component, ML.MAV_CMD_SET_MESSAGE_INTERVAL,
                                0, mid, int(1e6 / hz), 0, 0, 0, 0, 0)
    rel_alt, last_fix_t, boot_t = 0.0, None, 0.0

    def _status():
        if status_file:
            with open(status_file, "w") as fh:
                json.dump({"alarm_boot_t": st.alarm_boot_t, "blocks": len(st.blocks)}, fh)
    t_end = time.monotonic() + wall_timeout_s
    last_rx = time.monotonic()
    while (stop is None or not stop.is_set()) and time.monotonic() < t_end:
        msg = m.recv_match(type=["GPS_RAW_INT", "GLOBAL_POSITION_INT"], blocking=True, timeout=1)
        if msg is None:
            if time.monotonic() - last_rx > 15:  # link gone (vehicle/simulator stopped)
                break
            time.sleep(0.05)
            continue
        last_rx = time.monotonic()
        if msg.get_type() == "GLOBAL_POSITION_INT":
            rel_alt = msg.relative_alt / 1000.0
            boot_t = msg.time_boot_ms / 1000.0
            continue
        if msg.fix_type < 3 or msg.time_usec == last_fix_t:
            continue
        last_fix_t = msg.time_usec
        spd, cog = msg.vel / 100.0, math.radians(msg.cog / 100.0)
        n_before = len(st.blocks)
        fired = st.feed(msg.time_usec / 1e6, msg.lat, msg.lon, spd * math.cos(cog), spd * math.sin(cog), rel_alt > 3.0)
        if len(st.blocks) != n_before and len(st.blocks) % 10 == 0:
            _status()
        if fired:
            text = "ASTRA Shield-Companion: GNSS position/velocity inconsistent - possible spoofing"
            m.mav.statustext_send(ML.MAV_SEVERITY_CRITICAL, text.encode()[:50])
            st.alarm_boot_t = boot_t
            if log is not None:
                log.append((boot_t, "alarm"))
            _status()  # persist the alarm immediately
            if on_alarm == "land":
                m.set_mode("LAND")
    _status()
    m.close()
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--connect", required=True, help="pymavlink connection string, e.g. udp:0.0.0.0:14551")
    ap.add_argument("--cal", required=True, help="constants from `astra shield calibrate`")
    ap.add_argument("--on-alarm", choices=["alert", "land"], default="alert")
    a = ap.parse_args()
    st = monitor(a.connect, json.loads(open(a.cal).read()), on_alarm=a.on_alarm)
    print(json.dumps({"alarm_t": st.alarm_t, "blocks": len(st.blocks)}))


if __name__ == "__main__":
    main()


# ── Flow-Shield: the optical-flow witness channel (C2) online, on a companion computer ──────────────
@dataclass
class FlowShieldState:
    """Online version of the offline C2 channel (astra.detect): geometric flow model, tilt/speed nuisance
    correction, range whitening, 4 s block medians, CUSUM. Uses an A2 'gps+imu+flow' calibration as-is."""
    M: np.ndarray
    B: np.ndarray | None
    sigma_inv: np.ndarray
    k: float
    h: float
    block_s: float = 4.0
    ref_range: float = 30.0
    buf: list = field(default_factory=list)
    bstart: float | None = None
    cusum: float = 0.0
    alarm_t: float | None = None
    blocks: list = field(default_factory=list)
    raw: list = field(default_factory=list)  # (t, rN, rE) block residuals, for self-calibration

    def feed(self, t: float, comp_x: float, comp_y: float, quality: int, slant_m: float,
             roll: float, pitch: float, yaw: float, vn: float, ve: float, vd: float, airborne: bool) -> bool:
        if not airborne:
            self.buf, self.bstart = [], None
            return False
        if quality > 10 and slant_m > 2.0:
            cr, sr, cp, sp, cy, sy = (math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch),
                                      math.cos(yaw), math.sin(yaw))
            # R^T v (body x/y), same ZYX convention as astra.detect.features
            vbx = cp * cy * vn + cp * sy * ve - sp * vd
            vby = (sr * sp * cy - cr * sy) * vn + (sr * sp * sy + cr * cy) * ve + sr * cp * vd
            u = np.array([comp_x * slant_m, comp_y * slant_m])
            r = np.array([vbx, vby]) - self.M @ u
            if self.B is not None:
                X = np.array([1.0, roll, pitch, vbx, vby, pitch * vbx, roll * vby])
                r = r - X @ self.B
            r = r * (self.ref_range / max(slant_m, 5.0))
            self.buf.append(r)
        if self.bstart is None:
            self.bstart = t
        if t - self.bstart < self.block_s:
            return False
        fired = False
        if len(self.buf) >= 0.7 * self.block_s * 10 * 0.5:  # enough valid samples in the block (~10 Hz)
            rm = np.median(np.asarray(self.buf), axis=0)
            self.raw.append((t, float(rm[0]), float(rm[1])))
            q = float(rm @ self.sigma_inv @ rm)
            self.cusum = max(0.0, self.cusum + min(q, 100.0) - self.k)
            self.blocks.append((t, float(rm[0]), float(rm[1]), q, self.cusum))
            if self.cusum > self.h and self.alarm_t is None:
                self.alarm_t, fired = t, True
        self.buf, self.bstart = [], None
        return fired


def flow_monitor(conn: str, a2_flow_cal: dict, *, stop: threading.Event | None = None,
                 wall_timeout_s: float = 1e9) -> FlowShieldState:
    """With a2_flow_cal['h']['c2'] = inf it only collects residuals (calibration mode)."""
    """Companion-side C2 monitor. a2_flow_cal: the 'gps+imu+flow' entry of an A2 calibration."""
    c = a2_flow_cal
    st = FlowShieldState(np.asarray(c["flow_model"]), np.asarray(c["flow_nuisance"]) if c.get("flow_nuisance") else None,
                         np.asarray(c["sigma_inv"]["c2"]), float(c["k"]["c2"]), float(c["h"]["c2"]))
    m = mavutil.mavlink_connection(conn, source_system=254, source_component=192)
    m.wait_heartbeat(timeout=60)
    for mid, hz in ((ML.MAVLINK_MSG_ID_OPTICAL_FLOW, 10), (ML.MAVLINK_MSG_ID_DISTANCE_SENSOR, 10),
                    (ML.MAVLINK_MSG_ID_ATTITUDE, 10), (ML.MAVLINK_MSG_ID_GPS_RAW_INT, 5),
                    (ML.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 10)):
        m.mav.command_long_send(m.target_system, m.target_component, ML.MAV_CMD_SET_MESSAGE_INTERVAL,
                                0, mid, int(1e6 / hz), 0, 0, 0, 0, 0)
    att = (0.0, 0.0, 0.0)
    slant, rel_alt, vd, vn, ve, boot_t = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    t_end = time.monotonic() + wall_timeout_s
    last_rx = time.monotonic()
    while (stop is None or not stop.is_set()) and time.monotonic() < t_end:
        msg = m.recv_match(type=["OPTICAL_FLOW", "DISTANCE_SENSOR", "ATTITUDE", "GPS_RAW_INT", "GLOBAL_POSITION_INT"],
                           blocking=True, timeout=1)
        if msg is None:
            if time.monotonic() - last_rx > 15:
                break
            time.sleep(0.05)
            continue
        last_rx = time.monotonic()
        typ = msg.get_type()
        if typ == "ATTITUDE":
            att = (msg.roll, msg.pitch, msg.yaw)
        elif typ == "DISTANCE_SENSOR":
            slant = msg.current_distance / 100.0
        elif typ == "GLOBAL_POSITION_INT":
            rel_alt, vd, boot_t = msg.relative_alt / 1000.0, msg.vz / 100.0, msg.time_boot_ms / 1000.0
        elif typ == "GPS_RAW_INT" and msg.fix_type >= 3:
            spd, cog = msg.vel / 100.0, math.radians(msg.cog / 100.0)
            vn, ve = spd * math.cos(cog), spd * math.sin(cog)
        elif typ == "OPTICAL_FLOW":
            if st.feed(boot_t, msg.flow_comp_m_x, msg.flow_comp_m_y, msg.quality, slant, *att, vn, ve, vd, rel_alt > 3.0):
                m.mav.statustext_send(ML.MAV_SEVERITY_CRITICAL, b"ASTRA Flow-Shield: GNSS vs optical flow mismatch")
    m.close()
    return st
