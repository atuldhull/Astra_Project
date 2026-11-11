"""C4 (fixed-wing): air-data witness for GNSS velocity.

Wind triangle: v_ground = v_air + w. With GNSS velocity v_gps, true airspeed TAS, heading psi and pitch theta,
    w_raw = v_gps - k * TAS * cos(theta) * [cos psi, sin psi]
A velocity spoof of b (m/s, earth frame) shifts w_raw by exactly b. Real wind also changes, so the
detectable signal is a change of w faster/larger than real wind does it. k (airspeed scale) is fitted per
flight from heading diversity in an initial window, so heading-dependent scale error doesn't look like
wind change.

Loader works on PX4 ULog (real fixed-wing flights) and on ASTRA npz logs that carry the same series.
"""

from __future__ import annotations

import numpy as np

DT = 1.0  # s, analysis grid


def _q2eul(q0, q1, q2, q3):
    roll = np.arctan2(2 * (q0 * q1 + q2 * q3), 1 - 2 * (q1 * q1 + q2 * q2))
    pitch = np.arcsin(np.clip(2 * (q0 * q2 - q3 * q1), -1, 1))
    yaw = np.arctan2(2 * (q0 * q3 + q1 * q2), 1 - 2 * (q2 * q2 + q3 * q3))
    return roll, pitch, yaw


def load_ulog_fw(path) -> dict:
    """Return 1-Hz series: t, vn, ve (GNSS), tas, yaw, pitch, roll, airborne, px4 wind (wn, we)."""
    from pyulog import ULog

    u = ULog(str(path), ["vehicle_gps_position", "sensor_gps", "airspeed_validated", "airspeed",
                         "vehicle_attitude", "estimator_wind", "wind", "vehicle_local_position"])
    top = {}
    for d in u.data_list:
        if d.multi_id == 0:
            top.setdefault(d.name, d.data)
    g = top.get("vehicle_gps_position") or top.get("sensor_gps")
    a = top.get("airspeed_validated") or top.get("airspeed")
    att = top.get("vehicle_attitude")
    if g is None or a is None or att is None:
        raise ValueError("needs GNSS, airspeed and attitude topics")
    t0 = g["timestamp"][0]
    tg = (g["timestamp"] - t0) / 1e6
    t = np.arange(max(tg[0], 0.0), tg[-1], DT)
    f = lambda d, k: np.interp(t, (d["timestamp"] - t0) / 1e6, d[k])
    fix = f(g, "fix_type") if "fix_type" in g else np.full(len(t), 3.0)
    roll, pitch, yaw = _q2eul(*(f(att, f"q[{i}]") for i in range(4)))
    # unwrap-safe yaw interpolation: interpolate sin/cos
    sy, cy = np.interp(t, (att["timestamp"] - t0) / 1e6, np.sin(_q2eul(*(att[f"q[{i}]"] for i in range(4)))[2])), \
        np.interp(t, (att["timestamp"] - t0) / 1e6, np.cos(_q2eul(*(att[f"q[{i}]"] for i in range(4)))[2]))
    yaw = np.arctan2(sy, cy)
    tas = f(a, "true_airspeed_m_s")
    out = {"t": t, "vn": f(g, "vel_n_m_s"), "ve": f(g, "vel_e_m_s"), "tas": tas, "yaw": yaw, "pitch": pitch,
           "roll": roll, "fix": fix}
    lp = top.get("vehicle_local_position")
    agl = -f(lp, "z") if lp is not None else np.zeros(len(t))
    out["airborne"] = (tas > 8.0) & (fix >= 3) & np.isfinite(tas) & (agl - np.nanmin(agl[:30] if len(agl) > 30 else agl) > 10)
    w = top.get("estimator_wind") or top.get("wind")
    if w is not None:
        out["px4_wn"], out["px4_we"] = f(w, "windspeed_north"), f(w, "windspeed_east")
    return out


def wind_raw(s: dict, k: float = 1.0) -> np.ndarray:
    h = k * s["tas"] * np.cos(s["pitch"])
    return np.stack([s["vn"] - h * np.cos(s["yaw"]), s["ve"] - h * np.sin(s["yaw"])], axis=1)


def fit_scale(s: dict, mask: np.ndarray, win: int = 60) -> float:
    """Airspeed scale k that makes wind most constant within `win`-second windows (needs heading change)."""
    best, bk = np.inf, 1.0
    idx = np.nonzero(mask)[0]
    if len(idx) < win:
        return 1.0
    for k in np.arange(0.80, 1.25, 0.01):
        w = wind_raw(s, k)[idx]
        segs = [w[i:i + win] for i in range(0, len(w) - win + 1, win)]
        cost = sum(float(((seg - seg.mean(0)) ** 2).sum()) for seg in segs)
        if cost < best:
            best, bk = cost, float(k)
    return bk


def shift_series(s: dict, k: float, recent_s: float = 30.0, gap_s: float = 30.0, ref_s: float = 60.0):
    """|mean w over the last recent_s  -  mean w over [t - recent - gap - ref, t - recent - gap]| (m/s)."""
    w = wind_raw(s, k)
    air = s["airborne"] & np.isfinite(w).all(1)
    n = len(w)
    r, g, f = int(recent_s / DT), int(gap_s / DT), int(ref_s / DT)
    cs = np.vstack([np.zeros((1, 2)), np.cumsum(np.where(air[:, None], w, 0.0), 0)])
    ca = np.concatenate([[0], np.cumsum(air)])
    T, D = [], []
    for i in range(r + g + f, n):
        a0, a1 = i - r, i
        b0, b1 = i - r - g - f, i - r - g
        na, nb = ca[a1] - ca[a0], ca[b1] - ca[b0]
        if na < 0.8 * r or nb < 0.8 * f:
            continue
        D.append(float(np.hypot(*((cs[a1] - cs[a0]) / na - (cs[b1] - cs[b0]) / nb))))
        T.append(s["t"][i])
    return np.asarray(T), np.asarray(D)
