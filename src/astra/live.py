"""Live GNSS health from standard MAVLink telemetry (ArduPilot or PX4), no calibration needed.

Feeds on GPS_RAW_INT (+ GLOBAL_POSITION_INT for height) and applies the receiver-side checks that held up on real
attacks (benchmarks/jammertest-v1.md, real-gate-v9.md):

  * fix loss / satellite drop while airborne      -> jamming-like
  * position re-appearing impossibly far after an outage (100 m + 60 m/s x gap) -> spoofing-like
  * receiver-reported accuracy worse than 5 m     -> degraded (not an accusation)
  * optional ASTRA Shield CUSUM (needs `astra shield calibrate` output) -> spoofing-like

Sources: a live MAVLink connection (`udp:0.0.0.0:14550`, `COM5`, `/dev/ttyACM0`, ...) or a replay of a flight log, so
the screen can be tried without hardware.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from astra.forensics import HACC_DEGRADED_M, JUMP_MARGIN_M, JUMP_MAX_SPEED_MS, RF_SAT_FRAC

AIRBORNE_M = 3.0
OUTAGE_MIN_S = 3.0  # shorter dropouts are common on benign flights (real-gate-v6.md)


def _dist_m(lat1, lon1, lat2, lon2) -> float:
    dn = (lat2 - lat1) * 111_320.0
    de = (lon2 - lon1) * 111_320.0 * math.cos(math.radians(lat1))
    return math.hypot(dn, de)


@dataclass
class LiveHealth:
    shield_cal: dict | None = None
    events: list = field(default_factory=list)  # (t, kind, text); kind in jam | spoof | degraded | info
    hist: deque = field(default_factory=lambda: deque(maxlen=3000))  # (t, sats, hacc, fix)
    last: dict = field(default_factory=dict)
    _good: tuple | None = None  # (t, lat, lon) of the last good fix
    _lost_t: float | None = None
    _sats: deque = field(default_factory=lambda: deque(maxlen=300))
    _sat_low_t: float | None = None
    _degraded: bool = False
    _shield: object = None

    def __post_init__(self):
        if self.shield_cal:
            from astra.companion import ShieldState
            from astra.onboard import K_DESIGN
            c = self.shield_cal
            self._shield = ShieldState(np.asarray(c["sigma_inv"]), float(c.get("k", K_DESIGN)), float(c["h"]))

    def _event(self, t, kind, text):
        self.events.append((round(t, 1), kind, text))

    def feed(self, t: float, fix_type: int, lat: float, lon: float, sats: int, hacc_m: float | None,
             spd: float, cog_deg: float, rel_alt_m: float) -> None:
        air = rel_alt_m > AIRBORNE_M
        fix = fix_type >= 3 and abs(lat) > 1e-6
        self.hist.append((t, sats, hacc_m if hacc_m is not None else float("nan"), int(fix)))
        self.last = {"t": round(t, 1), "fix_type": int(fix_type), "sats": int(sats), "airborne": air,
                     "hacc_m": None if hacc_m is None else round(hacc_m, 1), "speed_ms": round(spd, 1),
                     "lat": round(lat, 6) if fix else None, "lon": round(lon, 6) if fix else None,
                     "height_m": round(rel_alt_m, 1)}
        if not fix:
            if self._lost_t is None:
                self._lost_t = t
            elif air and t - self._lost_t >= OUTAGE_MIN_S and not any(
                    e[1] == "jam" and e[0] >= self._lost_t for e in self.events):
                self._event(self._lost_t, "jam", "receiver lost its fix in flight")
            return
        if self._lost_t is not None:
            gap = t - self._lost_t
            if self._good is not None:
                d = _dist_m(self._good[1], self._good[2], lat, lon)
                if d > JUMP_MARGIN_M + JUMP_MAX_SPEED_MS * (t - self._good[0]):
                    self._event(t, "spoof", f"position jumped {d / 1000:.1f} km across a {gap:.0f} s outage")
            self._lost_t = None
            if self._shield is not None:  # restart the consistency window: never difference across an outage
                self._shield.hist.clear()
                self._shield.bn, self._shield.be, self._shield.bstart = [], [], None
        self._good = (t, lat, lon)
        if air:
            self._sats.append(sats)
            usual = float(np.median(self._sats)) if len(self._sats) >= 30 else None
            if usual and sats < RF_SAT_FRAC * usual:
                if self._sat_low_t is None:
                    self._sat_low_t = t
                elif t - self._sat_low_t >= OUTAGE_MIN_S and not any(
                        e[1] == "jam" and e[0] >= self._sat_low_t for e in self.events):
                    self._event(self._sat_low_t, "jam", f"satellites dropped {usual:.0f} -> {sats}")
            else:
                self._sat_low_t = None
        deg = hacc_m is not None and hacc_m > HACC_DEGRADED_M
        if deg and not self._degraded:
            self._event(t, "degraded", f"receiver reports {hacc_m:.0f} m accuracy")
        self._degraded = deg
        if self._shield is not None:
            c = math.radians(cog_deg)
            if self._shield.feed(t, int(round(lat * 1e7)), int(round(lon * 1e7)), spd * math.cos(c), spd * math.sin(c), air):
                self._event(t, "spoof", "ASTRA Shield: position and velocity disagree (possible slow spoof)")

    def state(self) -> str:
        kinds = {e[1] for e in self.events}
        if "spoof" in kinds:
            return "spoofing-like"
        if "jam" in kinds:
            return "jamming-like"
        if self._lost_t is not None or self._degraded:
            return "degraded"
        return "ok" if self.last else "waiting"

    def status(self) -> dict:
        h = list(self.hist)[-600:]
        return {"state": self.state(), "last": self.last, "events": self.events[-50:],
                "shield": None if self._shield is None else {"cusum": round(self._shield.cusum, 2),
                                                             "h": self._shield.h},
                "series": {"t": [r[0] for r in h], "sats": [r[1] for r in h],
                           "hacc": [None if r[2] != r[2] else r[2] for r in h], "fix": [r[3] for r in h]}}


class LiveSession:
    """Background reader feeding LiveHealth from MAVLink or from a replayed log."""

    def __init__(self, source: str, shield_cal: dict | None = None, replay_speed: float = 10.0):
        self.source, self.speed = source, replay_speed
        self.health = LiveHealth(shield_cal=shield_cal)
        self.error: str | None = None
        self.connected = False
        self.done = False
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()

    def stop(self):
        self._stop.set()

    def status(self) -> dict:
        s = self.health.status()
        s.update(source=self.source, connected=self.connected, done=self.done, error=self.error)
        return s

    def _run(self):
        try:
            if self.source.startswith("replay:"):
                self._replay(self.source[len("replay:"):])
            else:
                self._mavlink(self.source)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self.error = f"{type(exc).__name__}: {exc}"
        self.done = True

    def _replay(self, path: str):
        from astra.forensics import _load
        from pathlib import Path
        fl = _load(Path(path))
        g, pos = fl["GPS"], fl["POS"]
        acc = fl["GPA"]["HAcc"] if fl.has("GPA") else np.full(len(g["t"]), np.nan)
        rel = np.interp(g["t"], pos["t"], pos["RelHomeAlt"])
        air = fl.airborne(g["t"])
        rel = np.where(air, np.maximum(rel, AIRBORNE_M + 1), np.minimum(rel, 0.0))
        self.connected = True
        t0, w0 = float(g["t"][0]), time.monotonic()
        for i in range(len(g["t"])):
            if self._stop.is_set():
                return
            wait = (float(g["t"][i]) - t0) / self.speed - (time.monotonic() - w0)
            if wait > 0:
                time.sleep(min(wait, 1.0))
            ha = float(acc[i]) if np.isfinite(acc[i]) and 0 < acc[i] < 1e4 else None
            self.health.feed(float(g["t"][i]) - t0, int(g["Status"][i]), float(g["Lat"][i]), float(g["Lng"][i]),
                             int(g["NSats"][i]), ha, float(g["Spd"][i]), float(g["GCrs"][i]), float(rel[i]))

    def _mavlink(self, conn: str):
        from pymavlink import mavutil
        ml = mavutil.mavlink
        m = mavutil.mavlink_connection(conn, source_system=254, source_component=191)
        if m.wait_heartbeat(timeout=30) is None:
            raise TimeoutError(f"no MAVLink heartbeat on {conn} within 30 s")
        self.connected = True
        for mid in (ml.MAVLINK_MSG_ID_GPS_RAW_INT, ml.MAVLINK_MSG_ID_GLOBAL_POSITION_INT):
            m.mav.command_long_send(m.target_system, m.target_component, ml.MAV_CMD_SET_MESSAGE_INTERVAL,
                                    0, mid, 200000, 0, 0, 0, 0, 0)
        rel_alt, t0, last_rx = 0.0, time.monotonic(), time.monotonic()
        while not self._stop.is_set():
            msg = m.recv_match(type=["GPS_RAW_INT", "GLOBAL_POSITION_INT"], blocking=True, timeout=1)
            if msg is None:
                if time.monotonic() - last_rx > 15:
                    raise TimeoutError("telemetry stopped for 15 s")
                continue
            last_rx = time.monotonic()
            if msg.get_type() == "GLOBAL_POSITION_INT":
                rel_alt = msg.relative_alt / 1000.0
                continue
            hacc = getattr(msg, "h_acc", 0) or 0
            self.health.feed(time.monotonic() - t0, msg.fix_type, msg.lat / 1e7, msg.lon / 1e7,
                             msg.satellites_visible if msg.satellites_visible != 255 else 0,
                             hacc / 1000.0 if hacc else None, msg.vel / 100.0 if msg.vel != 65535 else 0.0,
                             msg.cog / 100.0 if msg.cog != 65535 else 0.0, rel_alt)
        m.close()
