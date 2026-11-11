"""C5: long-window displacement test (slow naive spoofs).

Over a window W, GNSS position change should equal the integral of GNSS-reported velocity. A naive
drag-off (position walks, velocity stays true) adds rate × W of unexplained displacement, while receiver
position error contributes only ~σ√2 (a few metres) once W exceeds its correlation time. So slow drags
that hide in 4-second blocks stand out over a minute: 0.25 m/s × 60 s = 15 m against ~3-9 m of benign
noise.

Design (frozen after dev-only prototyping on benign-v1 / attack-dev): W = 60 s, threshold = 1.25 × the
largest benign value seen in calibration flights.
"""

from __future__ import annotations

import numpy as np

from astra.geo import latlon_to_ne

WINDOW_S = 60.0
MARGIN = 1.25


def displacement_series(fl, window_s: float = WINDOW_S) -> tuple[np.ndarray, np.ndarray]:
    g = fl["GPS"]
    ok = g["Status"] >= 3
    if ok.sum() < 10:
        return np.zeros(0), np.zeros(0)
    t = g["t"][ok]
    n, e = latlon_to_ne(g["Lat"][ok][0], g["Lng"][ok][0], g["Lat"][ok], g["Lng"][ok])
    crs = np.radians(g["GCrs"][ok])
    vn, ve = g["Spd"][ok] * np.cos(crs), g["Spd"][ok] * np.sin(crs)
    dt = np.diff(t, prepend=t[0])
    In, Ie = np.cumsum(vn * dt), np.cumsum(ve * dt)
    air = np.interp(t, fl["POS"]["t"], fl["POS"]["RelHomeAlt"]) > 3
    j = np.searchsorted(t, t - window_s)
    D = np.hypot((n - n[j]) - (In - In[j]), (e - e[j]) - (Ie - Ie[j]))
    m = air & air[j] & (t - t[j] >= 0.9 * window_s)
    return t[m], D[m]


def calibrate(benign_flights, window_s: float = WINDOW_S, margin: float = MARGIN) -> dict:
    peaks = [float(D.max()) for _, D in (displacement_series(fl, window_s) for fl in benign_flights) if len(D)]
    return {"window_s": window_s, "threshold_m": margin * max(peaks), "n_flights": len(peaks)}


def first_alarm(fl, cal: dict) -> float | None:
    t, D = displacement_series(fl, cal["window_s"])
    k = np.nonzero(D > cal["threshold_m"])[0]
    return float(t[k[0]]) if len(k) else None
