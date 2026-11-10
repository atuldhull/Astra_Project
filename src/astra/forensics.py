"""Flight-log forensics: what happened to the GNSS during this flight, and when.

Output is a plain dict (JSON-friendly) with:
  * receiver health timeline (fix loss, satellite/accuracy degradation): jamming evidence
  * the stock autopilot's own alerts
  * A2 monitor alarm (if a calibration is available) and per-channel evidence
  * a classification with the evidence that supports it
  * if the log is from ASTRA SITL: the ground truth, for checking the diagnosis

Classification is rule-based and explainable (A3-lite). It never claims more than the evidence:
"no anomaly found" is not "no attack happened" (see docs/v4/05-DETECTION-PHYSICS.md §1).
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import numpy as np

from astra import logs
from astra.evaluate import ALERT_WORDS, CODE_NAMES


def _load(path: Path) -> logs.FlightLog:
    if path.suffix == ".npz":
        return logs.load_npz(path)
    if path.suffix.lower() == ".ulg":
        from astra.ulog import load_ulog
        return load_ulog(path)
    return logs.load(path)


def _bundled_calibration():
    try:
        txt = resources.files("astra.data").joinpath("a2-calibration.json").read_text()
    except (FileNotFoundError, ModuleNotFoundError):
        return None
    return json.loads(txt)


def _intervals(t: np.ndarray, mask: np.ndarray, min_len_s: float = 1.0) -> list[list[float]]:
    out, start = [], None
    for ti, m in zip(t, mask):
        if m and start is None:
            start = ti
        elif not m and start is not None:
            if ti - start >= min_len_s:
                out.append([round(float(start), 1), round(float(ti), 1)])
            start = None
    if start is not None and t[-1] - start >= min_len_s:
        out.append([round(float(start), 1), round(float(t[-1]), 1)])
    return out


def _step_residual(fl: logs.FlightLog):
    """Per-fix |Δp − v̄·Δt| (m), airborne only: a position jump the reported velocity doesn't explain."""
    from astra.geo import latlon_to_ne
    g = fl["GPS"]
    ok = g["Status"] >= 3
    if ok.sum() < 3:
        return np.zeros(0), np.zeros(0)
    t, la, lo = g["t"][ok], g["Lat"][ok], g["Lng"][ok]
    n, e = latlon_to_ne(la[0], lo[0], la, lo)
    crs = np.radians(g["GCrs"][ok])
    vn, ve = g["Spd"][ok] * np.cos(crs), g["Spd"][ok] * np.sin(crs)
    dt = np.diff(t)
    rn = np.diff(n) - 0.5 * (vn[1:] + vn[:-1]) * dt
    re = np.diff(e) - 0.5 * (ve[1:] + ve[:-1]) * dt
    pos = fl["POS"]
    air = np.interp(t[1:], pos["t"], pos["RelHomeAlt"]) > 3
    good = (dt > 0.05) & (dt < 0.5) & air
    return t[1:][good], np.hypot(rn, re)[good]


def diagnose(path: Path, cal_file: Path | None = None) -> dict:
    from astra.detect import features, monitor

    fl = _load(Path(path))
    gps = fl["GPS"]
    rep: dict = {"log": str(path), "is_sitl": fl.is_sitl}
    no_fix = gps["Status"] < 3
    low_sats = gps["NSats"] < 6
    rep["receiver"] = {
        "fix_lost_intervals_s": _intervals(gps["t"], no_fix),
        "low_satellite_intervals_s": _intervals(gps["t"], low_sats & ~no_fix),
        "min_sats_in_fix": int(np.nanmin(gps["NSats"][~no_fix])) if (~no_fix).any() else None,
    }
    if fl.has("GPA"):
        g = fl["GPA"]
        rep["receiver"]["max_reported_hacc_m"] = round(float(np.nanmax(g["HAcc"])), 2)
    rep["stock_alerts"] = [[round(t, 1), m] for t, m in fl.messages if any(w in m.lower() for w in ALERT_WORDS)]

    cal_all = json.loads(Path(cal_file).read_text()) if cal_file else _bundled_calibration()
    a2 = {"available": False}
    if cal_all:
        cfg = "gps+imu+flow" if fl.has("OF") and fl.has("RFND") else "gps+imu"
        cal = monitor.Calibration(**cal_all[cfg])
        try:
            ch = features.compute(fl)
            if cal.flow_model:
                features.apply_flow(ch, cal.flow_model, cal.flow_nuisance)
            det, stats = monitor.run(ch, cal)
            a2 = {"available": True, "config": cfg, "alarm": det.alarm,
                  "alarm_t": None if det.t_alarm is None else round(det.t_alarm, 1),
                  "first_channel": det.channel,
                  "first_by_channel": {k: (None if v is None else round(v, 1)) for k, v in det.first_by_channel.items()},
                  "peak_over_threshold": {k: round(float(np.nanmax(s)) / cal.h[k], 2) for k, s in stats.items()}}
        except ValueError as exc:
            a2 = {"available": False, "reason": str(exc)}
    else:
        a2["reason"] = "no bundled A2 calibration yet (run benchmarks/a2_eval.py --save-cal)"
    rep["a2_monitor"] = a2

    # ── evidence ────────────────────────────────────────────────────────────
    jam_iv = rep["receiver"]["fix_lost_intervals_s"] + rep["receiver"]["low_satellite_intervals_s"]
    spoof_ev: list[tuple[float, str]] = []
    if a2.get("alarm"):
        spoof_ev.append((a2["alarm_t"], f"A2 {a2['first_channel']}"))
    step_thr = (cal_all or {}).get("step", {}).get("thresh_m")
    if step_thr:
        st, ss = _step_residual(fl)
        hits = st[ss > step_thr]
        rep["position_steps"] = {"threshold_m": step_thr, "n": int(len(hits)),
                                 "max_m": round(float(ss.max()), 1) if len(ss) else None,
                                 "first_t": round(float(hits[0]), 1) if len(hits) else None}
        if len(hits):
            spoof_ev.append((float(hits[0]), "position step"))
    for t, m in rep["stock_alerts"]:
        if "glitch" in m.lower():
            spoof_ev.append((t, "stock: " + m))

    # Attribution: spoof-like evidence inside a jamming interval (or up to 30 s after it, while the
    # receiver re-acquires and the EKF resets) is a jamming artefact, not separate spoofing.
    def _in_jam(t):
        return any(a - 5.0 <= t <= b + 30.0 for a, b in jam_iv)

    spoof_outside = [(t, why) for t, why in spoof_ev if not _in_jam(t)]
    rep["evidence"] = {"jamming_intervals_s": jam_iv,
                       "spoofing_events": [[round(t, 1), w] for t, w in spoof_ev],
                       "spoofing_events_outside_jamming": [[round(t, 1), w] for t, w in spoof_outside]}
    jam, spoof = bool(jam_iv), bool(spoof_outside)
    if jam and not spoof:
        verdict = "jamming-like: receiver lost fix or satellites"
    elif spoof and not jam:
        verdict = f"spoofing-like: {spoof_outside[0][1]} while the receiver reported a healthy fix"
    elif jam and spoof:
        verdict = "mixed: receiver degradation and, separately, navigation inconsistency"
    else:
        verdict = ("no GNSS anomaly found by the available checks. Note: a slow, consistent spoof is not "
                   "observable without an independent witness sensor (docs/v4/05-DETECTION-PHYSICS.md)")
    rep["verdict"] = verdict

    if fl.is_sitl:
        rep["ground_truth"] = [{"model": CODE_NAMES.get(c, c), "start_s": round(s, 1), "end_s": round(e, 1)}
                               for s, e, c in fl.attack_windows()]
    return rep
