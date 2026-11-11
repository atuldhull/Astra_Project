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

# Receiver-reported horizontal accuracy above this (airborne) = receiver says it is degraded. Real benign
# PX4 flights: median worst 1.0 m, 95th pct 3.6 m (304 flights); simulated spoofs never above 2.2 m.
HACC_DEGRADED_M = 5.0
LOW_SAT_MIN_S = 3.0
TAKEOFF_RADIUS_M = 15.0


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


def takeoff_check(fl: logs.FlightLog, lat: float, lon: float, radius_m: float = TAKEOFF_RADIUS_M) -> dict | None:
    """Power-on spoofing check: GPS position just before take-off vs the operator-declared take-off point.

    Consistency monitors cannot see a spoof that is present from boot (docs/v4/05-DETECTION-PHYSICS.md §1);
    this compares against an absolute reference instead. radius_m = how well the operator knows the pad
    (map pin / phone GPS). Alarm when the offset exceeds radius_m + max(10 m, 3 x reported accuracy).
    """
    from astra.geo import latlon_to_ne
    g, pos = fl["GPS"], fl["POS"]
    air = pos["t"][pos["RelHomeAlt"] > 3]
    t_to = float(air[0]) if len(air) else float(g["t"][-1])
    sel = (g["Status"] >= 3) & (g["t"] <= t_to) & (g["t"] >= t_to - 10.0)
    if sel.sum() < 3:
        return None
    n, e = latlon_to_ne(lat, lon, np.median(g["Lat"][sel]), np.median(g["Lng"][sel]))
    hacc = None
    if fl.has("GPA"):
        a = fl["GPA"]
        av = a["HAcc"][(a["t"] <= t_to) & (a["t"] >= t_to - 10.0) & (a["HAcc"] > 0) & (a["HAcc"] < 1e4)]
        hacc = float(np.median(av)) if len(av) else None
    limit = radius_m + max(10.0, 3.0 * (hacc or 0.0))
    off = float(np.hypot(n, e))
    return {"declared": [lat, lon], "radius_m": radius_m, "takeoff_t": round(t_to, 1),
            "offset_m": round(off, 1), "reported_hacc_m": None if hacc is None else round(hacc, 2),
            "limit_m": round(limit, 1), "mismatch": off > limit}


def diagnose(path: Path, cal_file: Path | None = None, takeoff: tuple | None = None) -> dict:
    """takeoff: optional (lat, lon[, radius_m]) of the real take-off point, for the power-on spoofing check."""
    from astra.detect import features, monitor

    fl = _load(Path(path))
    gps = fl["GPS"]
    rep: dict = {"log": str(path), "is_sitl": fl.is_sitl}
    # Only airborne receiver events count: fix acquisition on the ground after boot is normal
    # (it produced 3 'jamming-like' verdicts on fresh real benign flights, real-gate-v3.md).
    pos = fl["POS"]
    air_g = np.interp(gps["t"], pos["t"], pos["RelHomeAlt"]) > 3
    no_fix = (gps["Status"] < 3) & air_g
    low_sats = (gps["NSats"] < 6) & air_g
    rep["receiver"] = {
        "fix_lost_intervals_s": _intervals(gps["t"], no_fix),
        # A dip to 5 satellites with the fix kept must last >= 3 s: 1-2 s dips are routine on real
        # benign flights (2 of 339 in real-gate-v5.md were labelled jamming-like by them).
        "low_satellite_intervals_s": _intervals(gps["t"], low_sats & ~no_fix, min_len_s=LOW_SAT_MIN_S),
        "min_sats_in_fix": int(np.nanmin(gps["NSats"][gps["Status"] >= 3])) if (gps["Status"] >= 3).any() else None,
        "degraded_accuracy_intervals_s": [],
    }
    if fl.has("GPA"):
        g = fl["GPA"]
        hv = np.where((g["HAcc"] > 0) & (g["HAcc"] < 1e4), g["HAcc"], np.nan)
        rep["receiver"]["max_reported_hacc_m"] = round(float(np.nanmax(hv)), 2) if np.isfinite(hv).any() else None
        air_a = np.interp(g["t"], pos["t"], pos["RelHomeAlt"]) > 3
        rep["receiver"]["degraded_accuracy_intervals_s"] = _intervals(
            g["t"], air_a & (np.nan_to_num(hv) > HACC_DEGRADED_M), min_len_s=0.0)
    # Receiver's own jamming/spoofing flags (u-blox via PX4 sensor_gps). On 137 real benign flights level 2
    # ('mitigated'/'indicated') appeared on 31% / 2.9% of flights, level 3 never: only level 3 is evidence.
    self_rep = {}
    for key, name in (("JamState", "jamming"), ("SpoofState", "spoofing")):
        if key in gps:
            v = np.nan_to_num(gps[key])
            self_rep[name] = {"max_level_airborne": int(v[air_g].max()) if air_g.any() else None,
                              "level3_intervals_s": _intervals(gps["t"], (v >= 3) & air_g, min_len_s=0.0)}
    if self_rep:
        rep["receiver"]["self_report"] = self_rep
    rep["stock_alerts"] = [[round(t, 1), m] for t, m in fl.messages if any(w in m.lower() for w in ALERT_WORDS)]

    cal_all = json.loads(Path(cal_file).read_text()) if cal_file else _bundled_calibration()
    a2 = {"available": False}
    if cal_all:
        # The bundled flow model is fitted on simulated sensors; real flow sensors need their own
        # calibration (`astra calibrate` on the airframe's benign logs, passed as cal_file).
        use_flow = fl.has("OF") and fl.has("RFND") and (fl.is_sitl or cal_file is not None)
        cfg = "gps+imu+flow" if use_flow else "gps+imu"
        cal = monitor.Calibration(**cal_all[cfg])
        try:
            ch = features.compute(fl)
            if cal.flow_model:
                features.apply_flow(ch, cal.flow_model, cal.flow_nuisance)
            gate = (cal_all or {}).get("real_gate", {})
            chans = list(cal.sigma_inv)
            ok_fix = gps["Status"] >= 3
            gps_dt = float(np.median(np.diff(gps["t"][ok_fix]))) if ok_fix.sum() > 2 else float("inf")
            skipped = {}
            if "c3" in chans and gps_dt > gate.get("c3_min_gps_interval_s", float("inf")):
                chans.remove("c3")
                skipped["c3"] = f"GPS logged every {gps_dt:.1f} s; C3 needs >= ~3 Hz"
            det, stats = monitor.run(ch, cal, chans)
            a2 = {"available": True, "config": cfg, "alarm": det.alarm, "skipped_channels": skipped,
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
    jam_iv = rep["receiver"]["fix_lost_intervals_s"] + rep["receiver"]["low_satellite_intervals_s"] \
        + self_rep.get("jamming", {}).get("level3_intervals_s", [])
    spoof_ev: list[tuple[float, str]] = []
    weak_ev: list[tuple[float, str]] = []
    strong_h = (cal_all or {}).get("real_gate", {}).get("c3_strong_h")
    if a2.get("alarm"):
        for ch_name, t_ch in a2["first_by_channel"].items():
            if t_ch is None:
                continue
            # C3 has heavier real-world tails than simulation: below the real-flight threshold it is
            # reported as weak evidence only, never as spoofing (benchmarks/real-gate-v3.md).
            if ch_name == "c3" and strong_h and a2["peak_over_threshold"]["c3"] * cal_all[a2["config"]]["h"]["c3"] < strong_h:
                weak_ev.append((t_ch, "A2 c3 (weak)"))
            else:
                spoof_ev.append((t_ch, f"A2 {ch_name}"))
    step_thr = (cal_all or {}).get("step", {}).get("thresh_m")
    if step_thr:
        st, ss = _step_residual(fl)
        hits = st[ss > step_thr]
        rep["position_steps"] = {"threshold_m": step_thr, "n": int(len(hits)),
                                 "max_m": round(float(ss.max()), 1) if len(ss) else None,
                                 "first_t": round(float(hits[0]), 1) if len(hits) else None}
        # Real receivers glitch by up to ~4 m with a healthy fix (499 public PX4 flights); spoofed jumps and
        # meaconing in simulation are >= 18 m. Steps below the strong level are weak evidence only.
        step_strong = (cal_all or {}).get("real_gate", {}).get("step_strong_m", 0.0)
        strong = st[ss > max(step_thr, step_strong)]
        if len(strong):
            spoof_ev.append((float(strong[0]), "position step"))
        elif len(hits):
            weak_ev.append((float(hits[0]), "position step (small)"))
    for t, m in rep["stock_alerts"]:
        if "glitch" in m.lower():
            spoof_ev.append((t, "stock: " + m))
    for a, _b in self_rep.get("spoofing", {}).get("level3_intervals_s", []):
        spoof_ev.append((a, "receiver self-report: multiple spoofing indications"))
    if takeoff is not None:
        tk = takeoff_check(fl, *takeoff)
        rep["takeoff_check"] = tk or {"available": False, "reason": "no GPS fix in the 10 s before take-off"}
        if tk and tk["mismatch"]:
            spoof_ev.append((tk["takeoff_t"], f"take-off position {tk['offset_m']:.0f} m from the declared pad"))

    # Attribution: spoof-like evidence inside a jamming interval (or up to 30 s after it, while the
    # receiver re-acquires and the EKF resets) is a jamming artefact, not separate spoofing.
    def _in_jam(t):
        return any(a - 5.0 <= t <= b + 30.0 for a, b in jam_iv)

    # Evidence while the receiver itself reports degraded accuracy is not called spoofing: it is
    # weak/inconclusive (real receivers do this in multipath; a spoofer usually reports a healthy fix).
    deg_iv = rep["receiver"]["degraded_accuracy_intervals_s"]
    spoof_ev.sort()
    for t, why in [e for e in spoof_ev if any(a - 5.0 <= e[0] <= b + 30.0 for a, b in deg_iv)]:
        spoof_ev.remove((t, why))
        weak_ev.append((t, why + " (receiver reported degraded accuracy)"))
    spoof_outside = [(t, why) for t, why in spoof_ev if not _in_jam(t)]
    rep["evidence"] = {"jamming_intervals_s": jam_iv,
                       "spoofing_events": [[round(t, 1), w] for t, w in spoof_ev],
                       "spoofing_events_outside_jamming": [[round(t, 1), w] for t, w in spoof_outside],
                       "weak_events": [[round(t, 1), w] for t, w in weak_ev]}
    jam, spoof = bool(jam_iv), bool(spoof_outside)
    if jam and not spoof:
        verdict = "jamming-like: receiver lost fix or satellites"
    elif spoof and not jam:
        verdict = f"spoofing-like: {spoof_outside[0][1]} while the receiver reported a healthy fix"
    elif jam and spoof:
        verdict = "mixed: receiver degradation and, separately, navigation inconsistency"
    elif weak_ev and not jam:
        verdict = ("inconclusive: weak GPS position/velocity inconsistency, below the level seen as "
                   "spoofing (also seen in a few real benign flights)")
    else:
        verdict = ("no GNSS anomaly found by the available checks. Note: a slow, consistent spoof is not "
                   "observable without an independent witness sensor (docs/v4/05-DETECTION-PHYSICS.md)")
    rep["verdict"] = verdict

    if fl.is_sitl:
        rep["ground_truth"] = [{"model": CODE_NAMES.get(c, c), "start_s": round(s, 1), "end_s": round(e, 1)}
                               for s, e, c in fl.attack_windows()]
    return rep
