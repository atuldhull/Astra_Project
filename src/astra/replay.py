"""Flight replay data for `astra ui`: three tracks on one clock.

  truth  where the vehicle really was (simulator only: SIM)
  gps    what the GNSS receiver reported (GPS, only with a 3D fix)
  est    where the autopilot believed it was (POS, the EKF output)

plus the attack windows (simulation ground truth), ASTRA's evidence and alarm time, satellites and height.
Times are seconds from the start of the log.
"""

from __future__ import annotations

import numpy as np

from astra.logs import FlightLog

ATTACK_NAMES = {1: "jamming (total denial)", 2: "jamming (intermittent)", 3: "jamming (chaotic)", 4: "jamming (degrading)",
                5: "spoofing (position jump)", 6: "spoofing (slow drag)", 7: "meaconing (replay)"}


def _r(a, nd=7):
    return [None if not np.isfinite(x) else round(float(x), nd) for x in a]


def track(fl: FlightLog, rep: dict | None = None, max_points: int = 1500) -> dict:
    g, pos = fl["GPS"], fl["POS"]
    t0 = float(min(g["t"][0], pos["t"][0]))
    t1 = float(max(g["t"][-1], pos["t"][-1]))
    dt = max(0.5, (t1 - t0) / max_points)
    t = np.arange(t0, t1, dt)

    def series(s, ok=None):
        lat, lon = np.asarray(s["Lat"], float), np.asarray(s["Lng"], float)
        good = np.isfinite(lat) & (np.abs(lat) > 1e-6) & np.isfinite(lon)
        if ok is not None:
            good &= ok
        if good.sum() < 2:
            return None
        st = s["t"][good]
        la, lo = np.interp(t, st, lat[good]), np.interp(t, st, lon[good])
        k = np.clip(np.searchsorted(st, t), 1, len(st) - 1)
        gap = np.minimum(np.abs(st[k] - t), np.abs(st[k - 1] - t)) > 2.0  # no data near this instant
        la[gap | (t < st[0]) | (t > st[-1])] = np.nan
        lo[np.isnan(la)] = np.nan
        return {"lat": _r(la), "lon": _r(lo)}

    fix = g["Status"] >= 3
    out = {"t": _r(t - t0, 2), "gps": series(g, fix), "est": series(pos),
           "truth": series(fl["SIM"]) if fl.has("SIM") else None,
           "sats": _r(np.interp(t, g["t"], g["NSats"]), 0),
           "fix": [int(x) for x in (np.interp(t, g["t"], fix.astype(float)) > 0.5)],
           "height": _r(np.interp(t, pos["t"], pos["RelHomeAlt"]), 1),
           "attacks": [{"start": round(a - t0, 1), "end": round(b - t0, 1), "name": ATTACK_NAMES.get(c, f"attack {c}")}
                       for a, b, c in fl.attack_windows()],
           "events": [], "alarm": None, "verdict": None}
    if rep:
        ev = rep["evidence"]
        evs = [(t_ - t0, "spoof", w) for t_, w in ev["spoofing_events"]]
        evs += [(a - t0, "jam", f"receiver lost fix or satellites until {b - t0:.0f} s")
                for a, b in ev["jamming_intervals_s"]]
        evs += [(t_ - t0, "weak", w) for t_, w in ev["weak_events"]]
        out["events"] = sorted(([round(a, 1), k, w] for a, k, w in evs), key=lambda e: e[0])
        strong = [e for e in out["events"] if e[1] in ("spoof", "jam")]
        out["alarm"] = strong[0][0] if strong else None
        out["verdict"] = rep["verdict"]
    return out
