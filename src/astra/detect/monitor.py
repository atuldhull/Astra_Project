"""A2 monitor (v2): block-averaged residual channels → per-channel CUSUM → fused alarm.

Why block averaging (v1 lesson): the 10 Hz residuals are strongly autocorrelated, so a per-sample
CUSUM accumulates benign wobble and needs enormous thresholds, and with drift k above the
attacked mean it can never detect a small shift. Averaging over B-second blocks makes block
residuals nearly independent and Gaussian, so standard CUSUM design applies:

    q_b = r̄_b^T Σ_B^{-1} r̄_b      ~ χ²(2), mean 2 under H0, mean 2 + δ² under a shift δ
    S_b = max(0, S_{b-1} + q_b − k), with k = 2 + δ_design²/2
    alarm when S_b > h

Calibration (benign flights only): Σ_B per channel; h = margin × max benign peak (and ≥ h_min).
The FAR is then *measured* on held-out benign flights, never assumed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import numpy as np

from astra.detect.features import DT, Channels

CHANNELS = ("c1", "c2", "c3")
BLOCK_S = {"c1": 2.0, "c2": 4.0, "c3": 4.0}
# Smallest shift each channel is designed to catch, in block-σ units. Larger = fewer, faster alarms.
DELTA_DESIGN = {"c1": 2.0, "c2": 1.0, "c3": 1.0}
C1_DETREND_TAU_S = 60.0  # removes the per-flight accel-bias offset from the Δv channel
H_MIN = 8.0


def _ewma(x: np.ndarray, tau_s: float) -> np.ndarray:
    a = DT / tau_s
    out = np.full_like(x, np.nan)
    acc, init = np.zeros(x.shape[1]), False
    for i, row in enumerate(x):
        if np.isfinite(row).all():
            acc = row.copy() if not init else (1 - a) * acc + a * row
            init = True
        if init:
            out[i] = acc
    return out


def residual(ch: Channels, name: str) -> np.ndarray | None:
    r = getattr(ch, name)
    if r is None:
        return None
    if name == "c1":
        r = r - _ewma(r, C1_DETREND_TAU_S)
    return r


ROBUST = {"c1": False, "c2": True, "c3": True}  # block median for channels with isolated spikes


def blocks(t: np.ndarray, r: np.ndarray, valid: np.ndarray, block_s: float, min_frac: float = 0.7,
           robust: bool = False):
    """Non-overlapping block means (or medians). Returns (t_end, value (B,2), ok (B,)).

    Medians: one spike (e.g. a single bad optical-flow frame, which at 40 m range is tens of m/s)
    must not poison a whole block. A sustained spoof bias moves the median just as it moves the mean.
    """
    n = int(round(block_s / DT))
    nb = len(t) // n
    if nb == 0:
        return np.zeros(0), np.zeros((0, 2)), np.zeros(0, bool)
    T = t[: nb * n].reshape(nb, n)[:, -1]
    R = r[: nb * n].reshape(nb, n, 2)
    V = (valid[: nb * n] & np.isfinite(r[: nb * n]).all(axis=1)).reshape(nb, n)
    cnt = V.sum(axis=1)
    if robust:
        import warnings
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-invalid blocks; masked by `ok` below
            Rm = np.nanmedian(np.where(V[..., None], R, np.nan), axis=1)
        Rm = np.nan_to_num(Rm)
    else:
        Rm = np.where(V[..., None], R, 0.0).sum(axis=1) / np.maximum(cnt, 1)[:, None]
    ok = cnt >= min_frac * n
    return T, Rm, ok


def _chan_blocks(ch: Channels, name: str):
    r = residual(ch, name)
    if r is None:
        return None
    valid = ch.airborne.copy()
    if name == "c2" and ch.c2_valid is not None:
        valid &= ch.c2_valid
    return blocks(ch.t, r, valid, BLOCK_S[name], robust=ROBUST[name])


def cusum(q: np.ndarray, k: float, ok: np.ndarray) -> np.ndarray:
    S, s = np.zeros(len(q)), 0.0
    for i in range(len(q)):
        if ok[i] and np.isfinite(q[i]):
            s = max(0.0, s + min(q[i], 100.0) - k)
        elif not ok[i]:
            s = s  # hold through short invalid gaps (e.g. flow dropout), don't reset evidence
        S[i] = s
    return S


@dataclass
class Calibration:
    sigma_inv: dict = field(default_factory=dict)
    h: dict = field(default_factory=dict)
    k: dict = field(default_factory=dict)
    block_s: dict = field(default_factory=dict)
    flow_model: list | None = None
    flow_nuisance: list | None = None
    n_flights: int = 0
    airborne_hours: float = 0.0
    margin: float = 1.25
    version: int = 2

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Calibration":
        return cls(**json.loads(s))


def _q(R: np.ndarray, sinv: np.ndarray) -> np.ndarray:
    return np.einsum("ni,ij,nj->n", R, sinv, R)


def calibrate(benign: list[Channels], channels=CHANNELS, margin: float = 1.25) -> Calibration:
    cal = Calibration(margin=margin, n_flights=len(benign))
    cal.airborne_hours = sum(float(c.airborne.sum()) * DT for c in benign) / 3600
    for name in channels:
        per = [b for b in (_chan_blocks(c, name) for c in benign) if b is not None]
        if not per:
            continue
        R = np.concatenate([Rm[ok] for _, Rm, ok in per])
        if len(R) < 50:
            continue
        cov = np.cov(R.T) + 1e-6 * np.eye(2)
        sinv = np.linalg.inv(cov)
        k = 2.0 + DELTA_DESIGN[name] ** 2 / 2.0
        peak = max(float(np.max(cusum(_q(Rm, sinv), k, ok), initial=0.0)) for _, Rm, ok in per)
        cal.sigma_inv[name] = sinv.tolist()
        cal.k[name] = k
        cal.block_s[name] = BLOCK_S[name]
        cal.h[name] = max(peak * margin, H_MIN)
    return cal


@dataclass
class Detection:
    alarm: bool
    t_alarm: float | None
    channel: str | None
    first_by_channel: dict


def run(ch: Channels, cal: Calibration, channels=None) -> tuple[Detection, dict]:
    channels = channels or list(cal.sigma_inv)
    first, stats = {}, {}
    for name in channels:
        if name not in cal.sigma_inv:
            continue
        b = _chan_blocks(ch, name)
        if b is None:
            continue
        T, Rm, ok = b
        S = cusum(_q(Rm, np.asarray(cal.sigma_inv[name])), cal.k[name], ok)
        stats[name] = S
        idx = np.nonzero(S > cal.h[name])[0]
        first[name] = float(T[idx[0]]) if len(idx) else None
    hits = {k: v for k, v in first.items() if v is not None}
    if not hits:
        return Detection(False, None, None, first), stats
    c = min(hits, key=hits.get)
    return Detection(True, hits[c], c, first), stats
