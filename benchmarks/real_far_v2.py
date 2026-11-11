"""Powered sim-to-real gate: all shipped checks on ~159 real benign PX4 flights (public logs, local only).

- shipped checks (C3 / position-step / diagnose / Shield sim constants): false alarms over ALL real flights
- C5 displacement: threshold calibrated on 99 real flights (v1's 39 + 60 of v2), FA on the other v2 flights,
  and detection on the simulated naive drag-offs (attack-test2) with that real-calibrated threshold
"""
import collections, json, statistics as st, warnings
from pathlib import Path
import numpy as np
from astra import logs
from astra.detect import displacement as c5, features, monitor
from astra.forensics import _step_residual, diagnose
from astra.onboard import replay_cusum, shield_blocks
from astra.ulog import load_ulog

warnings.filterwarnings("ignore")
v1 = sorted(Path("runs/px4real").glob("*.ulg"))
v2 = sorted(Path("runs/px4real2").glob("*.ulg"))
cal_all = json.loads(Path("src/astra/data/a2-calibration.json").read_text())
c3cal = monitor.Calibration(**cal_all["gps+imu"])
step_thr = cal_all["step"]["thresh_m"]
shield = json.loads(Path("runs/shield/shield_cal.json").read_text())
S = np.asarray(shield["sigma_inv"])

rows, skipped = [], []
for p in v1 + v2:
    try:
        fl = load_ulog(p)
        ch = features.compute(fl)
    except Exception as exc:  # noqa: BLE001
        skipped.append((p.name[:8], f"{type(exc).__name__}: {str(exc)[:50]}"))
        continue
    hours = float(ch.airborne.sum()) * features.DT / 3600
    if hours < 0.02:
        skipped.append((p.name[:8], "under 72 s airborne"))
        continue
    det, _ = monitor.run(ch, c3cal, ["c3"])
    _, ss = _step_residual(fl)
    T, B = shield_blocks(fl)
    sh = bool(len(B)) and bool((replay_cusum(np.einsum("ni,ij,nj->n", B, S, B)) > shield["h"]).any())
    t5, D5 = c5.displacement_series(fl)
    rows.append({"set": "v1" if p in v1 else "v2", "name": p.name[:8], "hours": hours, "c3": det.alarm,
                 "step": bool(len(ss)) and bool((ss > step_thr).any()), "shield": sh,
                 "verdict": diagnose(p)["verdict"], "c5_peak": float(D5.max()) if len(D5) else None})

H = sum(r["hours"] for r in rows)
v2rows = [r for r in rows if r["set"] == "v2"]
cal_rows = [r for r in rows if r["set"] == "v1"] + v2rows[:60]
test_rows = v2rows[60:]
thr = 1.25 * max(r["c5_peak"] for r in cal_rows if r["c5_peak"] is not None)
fa5 = sum((r["c5_peak"] or 0) > thr for r in test_rows)
g = collections.defaultdict(list)
for line in Path("runs/attack-test2/results.jsonl").read_text().splitlines():
    r = json.loads(line)
    if r["outcome"] == "error" or not r["scenario_id"].endswith("-n"):
        continue
    fl = logs.load_npz(Path("runs/attack-test2") / f"{r['scenario_id']}__s0" / "flight.npz")
    on = fl.attack_windows()[0][0]
    t = c5.first_alarm(fl, {"window_s": c5.WINDOW_S, "threshold_m": thr})
    g[r["scenario_id"].split("-")[-3]].append((t is not None and t >= on, None if t is None else t - on))
n = len(rows)
lines = ["# Sim-to-real gate v2: real benign PX4 flights (public logs, analysed locally)\n",
         f"{n} usable real quadrotor mission flights ({H:.1f} airborne h); {len(skipped)} unusable.\n",
         "| shipped check (simulation-calibrated) | real flights alarmed |", "|---|---|",
         f"| A2 C3 (GPS pos-vs-vel) | {sum(r['c3'] for r in rows)}/{n} |",
         f"| position-step check (1.0 m) | {sum(r['step'] for r in rows)}/{n} |",
         f"| Shield (simulation constants) | {sum(r['shield'] for r in rows)}/{n} |",
         f"| `astra diagnose` verdict ≠ 'no anomaly' | {sum(not r['verdict'].startswith('no GNSS anomaly') for r in rows)}/{n} |",
         f"\n**C5 displacement, real-calibrated:** threshold {thr:.2f} m (1.25 × worst of {len(cal_rows)} real flights). "
         f"Held-out real FA: **{fa5}/{len(test_rows)}**.\n",
         "| naive drag rate (simulated, attack-test2) | detected with the real-calibrated threshold | latency s (median) |",
         "|---|---|---|"]
for rate in sorted(g, key=lambda x: float(x[1:])):
    xs = g[rate]; lat = [l for ok, l in xs if ok]
    lines.append(f"| {rate[1:]} m/s | {sum(ok for ok, _ in xs)}/{len(xs)} | {st.median(lat):.0f} |" if lat else f"| {rate[1:]} m/s | 0/{len(xs)} | - |")
if skipped:
    lines += ["\nUnusable logs:"] + [f"- {k}: {w}" for k, w in skipped]
text = "\n".join(lines)
Path("benchmarks/real-far-v2.md").write_text(text + "\n", encoding="utf-8")
json.dump(rows, open("runs/real-far-v2-rows.json", "w"), indent=0)
print(text.encode("ascii", "replace").decode())
json.dump({"window_s": c5.WINDOW_S, "threshold_m": thr, "calibrated_on": f"{len(cal_rows)} real PX4 flights"},
          open("runs/c5-real-cal.json", "w"))
