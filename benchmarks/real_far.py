"""Sim-to-real check on REAL benign PX4 flights (public PX4 Flight Review logs).

Runs the GPS+IMU detectors calibrated on SIMULATED flights against real logs and reports false
alarms, plus residual noise statistics real vs simulated. Logs are analysed locally only and never
redistributed; only aggregate numbers are reported.

usage: python benchmarks/real_far.py ULOG_DIR --out benchmarks/real-far-v1.md
"""
from __future__ import annotations

import argparse
import collections
import json
import warnings
from pathlib import Path

import numpy as np

from astra import logs
from astra.detect import features, monitor
from astra.forensics import _step_residual, diagnose
from astra.ulog import load_ulog

warnings.filterwarnings("ignore")


def stats(ch, name):
    r = monitor.residual(ch, name)
    m = ch.airborne & np.isfinite(r).all(axis=1)
    return r[m]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--out")
    a = ap.parse_args()
    cal_all = json.loads(Path("src/astra/data/a2-calibration.json").read_text())
    cal = monitor.Calibration(**cal_all["gps+imu"])
    rows, skipped, R = [], [], collections.defaultdict(list)
    for p in sorted(Path(a.dir).glob("*.ulg")):
        try:
            fl = load_ulog(p)
            ch = features.compute(fl)
        except Exception as exc:  # noqa: BLE001
            skipped.append((p.name[:8], f"{type(exc).__name__}: {str(exc)[:60]}"))
            continue
        hours = float(ch.airborne.sum()) * features.DT / 3600
        if hours < 0.02:
            skipped.append((p.name[:8], "under 72 s airborne"))
            continue
        det, st = monitor.run(ch, cal, ["c1", "c3"])
        _, ss = _step_residual(fl)
        rep = diagnose(p)
        for nm in ("c1", "c3"):
            R[nm].append(stats(ch, nm))
        rows.append({"log": p.name[:8], "hours": hours, "alarm": det.alarm, "channel": det.channel,
                     "peak_over_h": {k: round(float(np.max(v, initial=0)) / cal.h[k], 2) for k, v in st.items()},
                     "max_step_m": round(float(ss.max()), 2) if len(ss) else None,
                     "step_hits": int((ss > cal_all["step"]["thresh_m"]).sum()) if len(ss) else 0,
                     "verdict": rep["verdict"].split(":")[0]})
    sim = collections.defaultdict(list)
    sys_dirs = sorted(Path("runs/benign-v3").glob("*__s0"))[:30]
    for d in sys_dirs:
        ch = features.compute(logs.load_npz(d / "flight.npz"))
        for nm in ("c1", "c3"):
            sim[nm].append(stats(ch, nm))
    H = sum(r["hours"] for r in rows)
    fa = sum(r["alarm"] for r in rows)
    lines = ["# Sim-to-real check: real benign PX4 flights vs simulation-calibrated detectors\n",
             f"{len(rows)} real quadrotor mission flights ({H:.2f} airborne h) from public PX4 Flight Review logs "
             f"(seeded random sample; {len(skipped)} unusable). Calibration: bundled A2 v7 (simulated receivers only).\n",
             f"- **A2 GPS+IMU false alarms: {fa}/{len(rows)} flights** "
             f"({fa / H:.2f}/h; simulated held-out was 0 in 7.2 h). By channel: {dict(collections.Counter(r['channel'] for r in rows if r['alarm']))}",
             f"- **Position-step check (1.0 m, sim-calibrated): {sum(r['step_hits'] > 0 for r in rows)}/{len(rows)} flights** had ≥ 1 hit; "
             f"median per-flight max step {np.median([r['max_step_m'] for r in rows if r['max_step_m'] is not None]):.2f} m",
             f"- `astra diagnose` verdicts: {dict(collections.Counter(r['verdict'] for r in rows))}",
             "\nResidual noise, real vs simulated (std per axis, airborne):\n",
             "| channel | simulated (benign-v3) | real (PX4 public) | ratio |", "|---|---|---|---|"]
    for nm in ("c1", "c3"):
        s_ = np.concatenate(sim[nm]).std(axis=0)
        r_ = np.concatenate(R[nm]).std(axis=0)
        lines.append(f"| {nm} | {np.round(s_, 3).tolist()} | {np.round(r_, 3).tolist()} | {np.round(r_ / s_, 1).tolist()} |")
    lines += ["\nPer flight (anonymised log-id prefix):\n", "| log | airborne h | alarm | channel | peak/h | max step m | step hits | verdict |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['log']} | {r['hours']:.2f} | {r['alarm']} | {r['channel'] or '-'} | {r['peak_over_h']} | "
                     f"{r['max_step_m']} | {r['step_hits']} | {r['verdict']} |")
    if skipped:
        lines += ["\nUnusable logs:"] + [f"- {k}: {w}" for k, w in skipped]
    text = "\n".join(lines)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
