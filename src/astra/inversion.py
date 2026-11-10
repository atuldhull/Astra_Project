"""A5: incident → scenario inversion.

From a flight log where a drag-off spoof was detected, estimate the attack (onset, rate, bearing,
naive vs consistent) and emit an ASTRA scenario that reproduces it, so the vendor can re-fly the
exact incident, change their configuration and re-test.

Physics used (see 05-DETECTION-PHYSICS):
  * naive drag: GPS position-derived velocity − reported velocity (channel C3) equals the spoof's
    velocity vector after onset; consistent drag leaves C3 ≈ 0
  * consistent drag with a flow witness: GPS velocity − flow velocity (C2, body frame) equals the bias;
    rotated back to NED with the vehicle yaw it gives rate and bearing
Onset: the last time the channel's CUSUM statistic was zero before the alarm (standard CUSUM
change-point estimate).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from astra.detect import features, monitor
from astra.detect.features import _interp


@dataclass
class Inversion:
    channel: str
    kind: str  # "naive" | "consistent"
    onset_s: float
    rate_ms: float
    bearing_deg: float
    alarm_s: float
    n_blocks: int

    def scenario_attack(self, after_arm_s: float | None = None) -> dict:
        start = {"after_arm_s": round(after_arm_s, 1)} if after_arm_s is not None else {"after_arm_s": 0.0}
        return {"model": "spoof_drag", "start": start, "duration_s": 3600, "rate_ms": round(self.rate_ms, 2),
                "bearing_deg": round(self.bearing_deg % 360, 1), "consistent": self.kind == "consistent"}


def _onset_from_cusum(T: np.ndarray, S: np.ndarray, alarm_idx: int) -> float:
    zeros = np.nonzero(S[: alarm_idx + 1] <= 1e-9)[0]
    return float(T[zeros[-1]]) if len(zeros) else float(T[0])


def invert(fl, cal: monitor.Calibration) -> Inversion | None:
    ch = features.compute(fl)
    if cal.flow_model:
        features.apply_flow(ch, cal.flow_model, cal.flow_nuisance)
    det, stats = monitor.run(ch, cal)
    if not det.alarm:
        return None
    name = det.channel
    T, Rm, ok = monitor._chan_blocks(ch, name)
    S = stats[name]
    ia = int(np.nonzero(S > cal.h[name])[0][0])
    onset = _onset_from_cusum(T, S, ia)
    post = ok & (T > onset) & (T <= T[ia] + 60)
    if post.sum() < 2:
        post = ok & (T > onset)
    if name == "c3":
        # residual is (position-rate − reported velocity) in NED, i.e. the naive spoof velocity
        v = np.median(Rm[post], axis=0)
        kind = "naive"
        vn, ve = float(v[0]), float(v[1])
    elif name == "c2":
        # body-frame residual (GPS − flow), un-whitened, rotated to NED with the vehicle yaw
        r = ch.c2.copy()
        if features.FLOW_WHITEN and "flow_range" in ch.meta:
            r = r / (features.FLOW_REF_RANGE_M / np.clip(ch.meta["flow_range"], 5.0, None))[:, None]
        att = fl["ATT"]
        yaw = np.radians(_interp(ch.t, att["t"], att["Yaw"]))
        n_ = r[:, 0] * np.cos(yaw) - r[:, 1] * np.sin(yaw)
        e_ = r[:, 0] * np.sin(yaw) + r[:, 1] * np.cos(yaw)
        m = (ch.t > onset) & (ch.t <= T[ia] + 60) & np.isfinite(n_) & ch.airborne
        vn, ve = float(np.median(n_[m])), float(np.median(e_[m]))
        kind = "consistent"
    else:
        return None
    return Inversion(name, kind, onset, math.hypot(vn, ve), math.degrees(math.atan2(ve, vn)) % 360,
                     float(T[ia]), int(post.sum()))
