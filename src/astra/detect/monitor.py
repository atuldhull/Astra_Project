"""A2 monitor: normalised residual channels → per-channel CUSUM → fused alarm.

Calibration uses benign flights only:
  * noise covariance Σ_c per channel (robust: clipped sample covariance)
  * CUSUM drift k_c is a fixed design constant (documented), threshold h_c is set so the
    calibration flights produce ZERO alarms, times a safety margin. The false-alarm rate is then
    *measured* on held-out benign flights, never assumed.

No attack data is used in calibration.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import numpy as np

from astra.detect.features import Channels, DT

CHANNELS = ("c1", "c2", "c3")
DESIGN_K = {"c1": 6.0, "c2": 4.0, "c3": 4.0}  # CUSUM drift in chi^2(2) units (H0 mean = 2)
C1_DETREND_TAU_S = 60.0  # removes per-flight accel-bias offset from the Δv channel


def _ewma(x: np.ndarray, tau_s: float) -> np.ndarray:
    a = DT / tau_s
    out = np.empty_like(x)
    acc = np.zeros(x.shape[1])
    init = False
    for i, row in enumerate(x):
        if np.isfinite(row).all():
            acc = row.copy() if not init else (1 - a) * acc + a * row
            init = True
        out[i] = acc if init else np.nan
    return out


def residual(ch: Channels, name: str) -> np.ndarray | None:
    r = getattr(ch, name)
    if r is None:
        return None
    if name == "c1":
        r = r - _ewma(r, C1_DETREND_TAU_S)
    return r


@dataclass
class Calibration:
    sigma_inv: dict = field(default_factory=dict)  # name -> 2x2 list
    h: dict = field(default_factory=dict)
    k: dict = field(default_factory=dict)
    flow_model: list | None = None
    n_flights: int = 0
    airborne_hours: float = 0.0
    margin: float = 1.25

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Calibration":
        return cls(**json.loads(s))


def _q(r: np.ndarray, sinv: np.ndarray) -> np.ndarray:
    q = np.einsum("ni,ij,nj->n", r, sinv, r)
    q[~np.isfinite(q)] = np.nan
    return q


def cusum(q: np.ndarray, k: float, valid: np.ndarray) -> np.ndarray:
    S = np.zeros_like(q)
    s = 0.0
    for i in range(len(q)):
        if not valid[i] or not np.isfinite(q[i]):
            s = 0.0 if not valid[i] else s
        else:
            s = max(0.0, s + min(q[i], 50.0) - k)  # clip single-sample outliers
        S[i] = s
    return S


def calibrate(benign: list[Channels], channels=CHANNELS, margin: float = 1.25) -> Calibration:
    cal = Calibration(margin=margin, n_flights=len(benign))
    cal.airborne_hours = sum(float(c.airborne.sum()) * DT for c in benign) / 3600
    for name in channels:
        rs = []
        for c in benign:
            r = residual(c, name)
            if r is None:
                continue
            m = c.airborne & np.isfinite(r).all(axis=1)
            rs.append(r[m])
        if not rs:
            continue
        R = np.concatenate(rs)
        lim = np.percentile(np.abs(R), 99.5, axis=0)
        Rc = R[(np.abs(R) <= lim).all(axis=1)]
        cov = np.cov(Rc.T) + 1e-6 * np.eye(2)
        sinv = np.linalg.inv(cov)
        cal.sigma_inv[name] = sinv.tolist()
        cal.k[name] = DESIGN_K[name]
        peak = 0.0
        for c in benign:
            r = residual(c, name)
            if r is None:
                continue
            S = cusum(_q(r, sinv), cal.k[name], c.airborne)
            peak = max(peak, float(np.nanmax(S)) if len(S) else 0.0)
        cal.h[name] = max(peak * margin, 10.0)
    return cal


@dataclass
class Detection:
    alarm: bool
    t_alarm: float | None
    channel: str | None
    first_by_channel: dict


def run(ch: Channels, cal: Calibration, channels=None) -> tuple[Detection, dict]:
    channels = channels or list(cal.sigma_inv)
    first: dict = {}
    stats: dict = {}
    for name in channels:
        if name not in cal.sigma_inv:
            continue
        r = residual(ch, name)
        if r is None:
            continue
        S = cusum(_q(r, np.asarray(cal.sigma_inv[name])), cal.k[name], ch.airborne)
        stats[name] = S
        idx = np.nonzero(S > cal.h[name])[0]
        first[name] = float(ch.t[idx[0]]) if len(idx) else None
    hits = {k: v for k, v in first.items() if v is not None}
    if not hits:
        return Detection(False, None, None, first), stats
    ch_name = min(hits, key=hits.get)
    return Detection(True, hits[ch_name], ch_name, first), stats
