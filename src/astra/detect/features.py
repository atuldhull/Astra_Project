"""Residual channels computed from an ordinary ArduPilot log on a uniform 10 Hz grid.

Only fields every ArduPilot log has (GPS, IMU, ATT) are needed for C1/C3.
C2 additionally needs an optical-flow sensor + downward rangefinder (OF, RFND).
Nothing here uses simulator truth (SIM/ASTK), so it runs unchanged on real flight logs.

Conventions: NED earth frame, body x forward / y right / z down.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from astra.geo import latlon_to_ne
from astra.logs import FlightLog

G = 9.80665
FLOW_WHITEN = True  # v7 (range whitening of the flow channel)
FLOW_REF_RANGE_M = 30.0
DT = 0.1  # 10 Hz analysis grid


@dataclass
class Channels:
    t: np.ndarray
    airborne: np.ndarray  # bool mask: analysis valid
    c1: np.ndarray  # (N,2) Δv_gps - Δv_imu over window W1 (m/s)
    c3: np.ndarray  # (N,2) v_from_gps_position - v_gps_reported (m/s)
    c2: np.ndarray | None  # (N,2) v_gps_body - v_flow_body (m/s), NaN where flow invalid
    c2_valid: np.ndarray | None
    meta: dict = field(default_factory=dict)


def _interp(t, tp, fp):
    return np.interp(t, tp, fp, left=np.nan, right=np.nan)


def _rot_body_to_ned(roll, pitch, yaw):
    """Rotation matrices (N,3,3) from ZYX Euler angles in radians."""
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    R = np.empty(roll.shape + (3, 3))
    R[..., 0, 0] = cp * cy
    R[..., 0, 1] = sr * sp * cy - cr * sy
    R[..., 0, 2] = cr * sp * cy + sr * sy
    R[..., 1, 0] = cp * sy
    R[..., 1, 1] = sr * sp * sy + cr * cy
    R[..., 1, 2] = cr * sp * sy - sr * cy
    R[..., 2, 0] = -sp
    R[..., 2, 1] = sr * cp
    R[..., 2, 2] = cr * cp
    return R


def _window_diff(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full_like(x, np.nan)
    out[n:] = x[n:] - x[:-n]
    return out


def compute(fl: FlightLog, w1_s: float = 3.0, pos_vel_s: float = 2.0,
            flow_model: np.ndarray | None = None) -> Channels:
    gps, imu, att = fl["GPS"], fl["IMU"], fl["ATT"]
    ok = gps["Status"] >= 3
    if ok.sum() < 20:
        raise ValueError("not enough 3D-fix GPS samples")
    gt = gps["t"][ok]
    lat0, lon0 = gps["Lat"][ok][0], gps["Lng"][ok][0]
    gn, ge = latlon_to_ne(lat0, lon0, gps["Lat"][ok], gps["Lng"][ok])
    crs = np.radians(gps["GCrs"][ok])
    gvn, gve = gps["Spd"][ok] * np.cos(crs), gps["Spd"][ok] * np.sin(crs)

    t = np.arange(gt[0], gt[-1], DT)
    n = len(t)
    # GPS reported velocity and position on the grid (zero-order hold of the latest fix is what the
    # autopilot sees; linear interpolation is close enough for residual statistics).
    vn, ve = _interp(t, gt, gvn), _interp(t, gt, gve)
    pn, pe = _interp(t, gt, gn), _interp(t, gt, ge)

    # IMU specific force -> NED kinematic acceleration
    roll = np.radians(_interp(imu["t"], att["t"], att["Roll"]))
    pitch = np.radians(_interp(imu["t"], att["t"], att["Pitch"]))
    yaw = np.radians(_interp(imu["t"], att["t"], att["Yaw"]))
    R = _rot_body_to_ned(roll, pitch, yaw)
    f_body = np.stack([imu["AccX"], imu["AccY"], imu["AccZ"]], axis=-1)
    a_ned = np.einsum("nij,nj->ni", R, f_body)
    a_ned[:, 2] += G
    good = np.isfinite(a_ned).all(axis=1)
    it, a_ned = imu["t"][good], a_ned[good]
    # cumulative integral of horizontal acceleration, then sampled on the grid
    dv_cum = np.zeros((len(it), 2))
    dt_imu = np.diff(it, prepend=it[0])
    dv_cum[:, 0] = np.cumsum(a_ned[:, 0] * dt_imu)
    dv_cum[:, 1] = np.cumsum(a_ned[:, 1] * dt_imu)
    ivn, ive = _interp(t, it, dv_cum[:, 0]), _interp(t, it, dv_cum[:, 1])

    k1 = int(round(w1_s / DT))
    c1 = np.stack([_window_diff(vn, k1) - _window_diff(ivn, k1),
                   _window_diff(ve, k1) - _window_diff(ive, k1)], axis=1)

    # GPS-position-derived velocity (central difference over pos_vel_s) vs reported velocity
    k3 = max(1, int(round(pos_vel_s / DT / 2)))
    pvn = np.full(n, np.nan)
    pve = np.full(n, np.nan)
    pvn[k3:-k3] = (pn[2 * k3:] - pn[:-2 * k3]) / (2 * k3 * DT)
    pve[k3:-k3] = (pe[2 * k3:] - pe[:-2 * k3]) / (2 * k3 * DT)
    c3 = np.stack([pvn - vn, pve - ve], axis=1)
    # (Tried: normalising c3 by reported hAcc. It raised held-out false alarms 0 -> 3 in 7.5 h,
    # because c3 noise is dominated by receiver *velocity* noise, which hAcc doesn't track. Reverted.)

    # airborne mask from the autopilot's own relative altitude
    pos = fl["POS"]
    rel = _interp(t, pos["t"], pos["RelHomeAlt"])
    airborne = np.nan_to_num(rel, nan=0.0) > 3.0

    c2 = c2_valid = None
    if fl.has("OF") and fl.has("RFND"):
        vd = _interp(t, gt, gps["VZ"][ok])
        c2, c2_valid, u, vb, d = _flow_channel(fl, t, vn, ve, vd, flow_model)
        meta_flow = {"flow_regressors": u, "gps_body_vel": vb, "c2_nuisance_X": _nuisance_X(fl, t, vb),
                     "flow_range": d}
    else:
        meta_flow = {}
    return Channels(t, airborne, c1, c3, c2, c2_valid,
                    meta={"vn": vn, "ve": ve, "pn": pn, "pe": pe, **meta_flow})


def flow_regressors(fl: FlightLog, t: np.ndarray):
    """u = (flow rate - body rate) * slant range, per body axis; plus validity mask and attitude.

    Geometry (v2): a body-fixed downward flow sensor sees the body-frame velocity component
    perpendicular to its boresight, divided by the slant range along the boresight, which is what
    a body-fixed rangefinder measures. So the regressor uses the raw range (not a cos-corrected
    height), and the GPS side uses the full 3-D velocity rotated into the body frame (v1 used yaw
    only, which is wrong at the 20-30 deg cruise tilts multicopters fly at).
    """
    of, rf, att = fl["OF"], fl["RFND"], fl["ATT"]
    fx, fy = _interp(t, of["t"], of["flowX"]), _interp(t, of["t"], of["flowY"])
    bx, by = _interp(t, of["t"], of["bodyX"]), _interp(t, of["t"], of["bodyY"])
    q = _interp(t, of["t"], of["Qual"])
    d = _interp(t, rf["t"], rf["Dist"])
    st = _interp(t, rf["t"], rf["Stat"])
    R = _rot_body_to_ned(*(np.radians(_interp(t, att["t"], att[k])) for k in ("Roll", "Pitch", "Yaw")))
    u = np.stack([(fx - bx) * d, (fy - by) * d], axis=1)
    valid = (q > 10) & (np.round(st) == 4) & (d > 2.0) & np.isfinite(u).all(axis=1)
    return u, valid, R, d


def _flow_channel(fl, t, vn, ve, vd, flow_model):
    u, valid, R, d = flow_regressors(fl, t)
    v_ned = np.stack([vn, ve, vd], axis=1)
    vb = np.einsum("nji,nj->ni", R, v_ned)[:, :2]  # R^T v: body-frame x/y velocity
    valid &= np.isfinite(vb).all(axis=1)
    M = flow_model if flow_model is not None else np.array([[0.0, 1.0], [-1.0, 0.0]])
    c2 = vb - u @ M.T
    c2[~valid] = np.nan
    return c2, valid, u, vb, d


def fit_flow_model(chs: list[Channels]) -> np.ndarray:
    """Least-squares 2x2 map from flow regressors to GPS body velocity, on benign flights only.

    Learned (not hard-coded) so sensor mounting/sign conventions of a given airframe are absorbed.
    """
    U, V = [], []
    for c in chs:
        if "flow_regressors" not in c.meta:
            continue
        m = c.c2_valid & c.airborne & np.isfinite(c.meta["gps_body_vel"]).all(axis=1)
        U.append(c.meta["flow_regressors"][m])
        V.append(c.meta["gps_body_vel"][m])
    U, V = np.concatenate(U), np.concatenate(V)
    # Flow is a cross product (omega x r): v_x = a*u_y, v_y = -a*u_x for one sensor gain a.
    # Fitting the full 2x2 is ill-posed because a copter yaws into its direction of travel, so there
    # is almost no lateral motion to learn from.
    # Separate forward/lateral gains are allowed (sensor optics/mounting can differ per axis), but the
    # lateral gain falls back to the forward one when there is too little lateral motion to fit it.
    ax = float(U[:, 1] @ V[:, 0] / (U[:, 1] @ U[:, 1]))
    lat_motion = float(np.std(V[:, 1]))
    ay = float(-U[:, 0] @ V[:, 1] / (U[:, 0] @ U[:, 0])) if lat_motion > 0.5 else ax
    return np.array([[0.0, ax], [-ay, 0.0]])


def _nuisance_X(fl: FlightLog, t: np.ndarray, vb: np.ndarray) -> np.ndarray:
    """Regressors for the flow channel's systematic error (tilt and speed coupling)."""
    att = fl["ATT"]
    roll = np.radians(_interp(t, att["t"], att["Roll"]))
    pitch = np.radians(_interp(t, att["t"], att["Pitch"]))
    return np.column_stack([np.ones_like(roll), roll, pitch, vb[:, 0], vb[:, 1],
                            pitch * vb[:, 0], roll * vb[:, 1]])


def fit_flow_nuisance(chs: list[Channels]) -> np.ndarray:
    """Least-squares (7x2) model of the benign flow residual. Benign flights only."""
    X, Y = [], []
    for c in chs:
        if c.c2 is None:
            continue
        Xc = c.meta["c2_nuisance_X"]
        m = c.airborne & c.c2_valid & np.isfinite(c.c2).all(axis=1) & np.isfinite(Xc).all(axis=1)
        X.append(Xc[m]); Y.append(c.c2[m])
    B, *_ = np.linalg.lstsq(np.concatenate(X), np.concatenate(Y), rcond=None)
    return B


def apply_flow(ch: Channels, M: np.ndarray, B: np.ndarray | None = None) -> Channels:
    """(Re)compute c2 for a fitted flow model M and optional nuisance model B."""
    if ch.c2 is None:
        return ch
    u, vb = ch.meta["flow_regressors"], ch.meta["gps_body_vel"]
    c2 = vb - u @ np.asarray(M).T
    if B is not None:
        c2 = c2 - ch.meta["c2_nuisance_X"] @ np.asarray(B)
    if FLOW_WHITEN and "flow_range" in ch.meta:
        # v7: flow noise is proportional to slant range (angular-rate noise x range), so whiten by it.
        c2 = c2 * (FLOW_REF_RANGE_M / np.clip(ch.meta["flow_range"], 5.0, None))[:, None]
    c2[~ch.c2_valid] = np.nan
    ch.c2 = c2
    return ch
