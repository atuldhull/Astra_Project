"""Ground-truth evaluation of a SITL flight log.

For each attack window (from the ASTK label) this measures:
  * how far the autopilot's belief (POS) drifted from truth (SIM)
  * L0 baseline detection = what the stock autopilot itself noticed:
      - operator-visible: a navigation-health STATUSTEXT
      - internal: EKF3 position or velocity innovation test ratio > 1.0
    and the latency from attack onset.

These L0 numbers are the baseline every ASTRA detector is compared against.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from astra.geo import latlon_to_ne
from astra.logs import FlightLog

ALERT_WORDS = (
    "gps glitch", "ekf variance", "ekf failsafe", "gps lost", "position lost",
    "bad gps", "ekf primary changed", "gps unhealthy", "lane switch", "failsafe",
    "glitch", "compass variance",
)
CODE_NAMES = {1: "jam_denial", 2: "jam_intermittent", 3: "jam_chaotic", 4: "jam_degrade",
              5: "spoof_jump", 6: "spoof_drag", 7: "meaconing"}


@dataclass
class WindowEval:
    model: str
    start_s: float
    end_s: float
    max_nav_error_m: float
    nav_error_at_end_m: float
    l0_alert: bool
    l0_alert_latency_s: float | None
    l0_alert_text: str | None
    l0_ratio: bool
    l0_ratio_latency_s: float | None
    l0_ratio_peak: float
    l0_detected_during: bool  # alert or ratio>1 strictly inside the attack window (the honest metric)
    l0_detect_latency_s: float | None  # first in-window detection, either channel
    l0_release_only: bool  # noticed only when the attacker stopped (snap-back), i.e. too late


def nav_error_series(fl: FlightLog) -> tuple[np.ndarray, np.ndarray]:
    """|truth - belief| horizontal error (m) at SIM timestamps."""
    sim, pos = fl["SIM"], fl["POS"]
    lat0, lon0 = float(sim["Lat"][0]), float(sim["Lng"][0])
    tn, te = latlon_to_ne(lat0, lon0, sim["Lat"], sim["Lng"])
    pn, pe = latlon_to_ne(lat0, lon0, np.interp(sim["t"], pos["t"], pos["Lat"]),
                          np.interp(sim["t"], pos["t"], pos["Lng"]))
    return sim["t"], np.hypot(tn - pn, te - pe)


def evaluate(fl: FlightLog, grace_s: float = 5.0) -> list[WindowEval]:
    if not fl.is_sitl:
        raise ValueError("ground-truth evaluation needs a SITL log (SIM + ASTK)")
    t_err, err = nav_error_series(fl)
    x4 = fl["XKF4"]
    ratio = np.fmax(x4["SP"], x4["SV"])
    alerts = [(t, m) for t, m in fl.messages if any(w in m.lower() for w in ALERT_WORDS)]
    out = []
    for s, e, code in fl.attack_windows():
        win = (t_err >= s) & (t_err <= e)
        hit_alert = next(((t, m) for t, m in alerts if s <= t <= e + grace_s), None)
        rmask = (x4["t"] >= s) & (x4["t"] <= e + grace_s)
        over = np.nonzero(rmask & (ratio > 1.0))[0]
        out.append(WindowEval(
            model=CODE_NAMES.get(code, str(code)),
            start_s=round(s, 2), end_s=round(e, 2),
            max_nav_error_m=round(float(err[win].max()), 2) if win.any() else math.nan,
            nav_error_at_end_m=round(float(np.interp(e, t_err, err)), 2),
            l0_alert=hit_alert is not None,
            l0_alert_latency_s=round(hit_alert[0] - s, 2) if hit_alert else None,
            l0_alert_text=hit_alert[1] if hit_alert else None,
            l0_ratio=len(over) > 0,
            l0_ratio_latency_s=round(float(x4["t"][over[0]] - s), 2) if len(over) else None,
            l0_ratio_peak=round(float(np.nanmax(ratio[rmask])), 3) if rmask.any() else math.nan,
            **_during(s, e, hit_alert, x4["t"], ratio, alerts),
        ))
    return out


def evaluate_dicts(fl: FlightLog) -> list[dict]:
    return [asdict(w) for w in evaluate(fl)]


def _during(s, e, hit_alert, rt, ratio, alerts) -> dict:
    in_alert = next((t for t, _ in alerts if s <= t <= e), None)
    idx = np.nonzero((rt >= s) & (rt <= e) & (ratio > 1.0))[0]
    in_ratio = float(rt[idx[0]]) if len(idx) else None
    cands = [x for x in (in_alert, in_ratio) if x is not None]
    first = min(cands) if cands else None
    after = hit_alert is not None or bool(np.any((rt > e) & (ratio > 1.0) & (rt <= e + 5.0)))
    return {
        "l0_detected_during": first is not None,
        "l0_detect_latency_s": round(first - s, 2) if first is not None else None,
        "l0_release_only": first is None and after,
    }
