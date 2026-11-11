"""Real-aware threshold floor for the shipped GPS-only checks (C3 CUSUM, position-step).

Statistics (Σ, k, block length) stay as designed in simulation. Only thresholds get a floor:
    h_new = max(h_sim, 1.25 × worst value over the REAL calibration split)
Split (fixed before looking at the result): real calibration = px4real (39) + first 60 of px4real2 (sorted by
name); held-out = remaining 60 of px4real2. Scored once. Detection cost measured on attack-test2 (simulation,
GPS+IMU only), old vs new thresholds on identical flights.
"""
import collections, json, warnings
from pathlib import Path
import numpy as np
from astra import logs
from astra.detect import features, monitor
from astra.forensics import _step_residual
from astra.ulog import load_ulog

warnings.filterwarnings("ignore")
MARGIN = 1.25
cal_all = json.loads(Path("src/astra/data/a2-calibration.json").read_text())
c3 = monitor.Calibration(**cal_all["gps+imu"])
h_sim, step_sim = c3.h["c3"], cal_all["step"]["thresh_m"]


def peaks(fl):
    ch = features.compute(fl)
    _, st = monitor.run(ch, c3, ["c3"])
    _, ss = _step_residual(fl)
    return (float(np.nanmax(st["c3"])) if "c3" in st and len(st["c3"]) else 0.0,
            float(ss.max()) if len(ss) else 0.0)


v1 = sorted(Path("runs/px4real").glob("*.ulg"))
v2 = sorted(Path("runs/px4real2").glob("*.ulg"))
calset, testset = v1 + v2[:60], v2[60:]
P = {p: peaks(load_ulog(p)) for p in calset + testset}
h_new = max(h_sim, MARGIN * max(P[p][0] for p in calset))
step_new = max(step_sim, MARGIN * max(P[p][1] for p in calset))


def fa(paths, h, s):
    return sum(P[p][0] > h or P[p][1] > s for p in paths)


rows = collections.defaultdict(lambda: [0, 0, 0])  # (kind, rate) -> [n, old, new]
for line in Path("runs/attack-test2/results.jsonl").read_text().splitlines():
    r = json.loads(line)
    if r["outcome"] == "error":
        continue
    fl = logs.load_npz(Path("runs/attack-test2") / f"{r['scenario_id']}__s0" / "flight.npz")
    w = fl.attack_windows()
    if not w:
        continue
    on, off, _ = w[0]
    ch = features.compute(fl)
    _, st = monitor.run(ch, c3, ["c3"])
    T, _, _ = monitor._chan_blocks(ch, "c3")
    S = st.get("c3", np.zeros(0))
    ts, ss = _step_residual(fl)
    dur = lambda tt: (tt >= on) & (tt <= off)

    def hit(h, s):
        return bool(((S > h) & dur(T)).any()) or bool(((ss > s) & dur(ts)).any())

    kind = "naive" if r["scenario_id"].endswith("-n") else "consistent" if r["scenario_id"].endswith("-c") else "other"
    key = (kind, r["scenario_id"].split("-")[-3] if kind != "other" else "-")
    rows[key][0] += 1
    rows[key][1] += hit(h_sim, step_sim)
    rows[key][2] += hit(h_new, step_new)

out = ["# Real-aware threshold floor (GPS-only checks)\n",
       f"C3 h: {h_sim:.1f} (sim) -> **{h_new:.1f}**; step: {step_sim:.2f} m -> **{step_new:.2f} m** "
       f"(1.25 × worst of {len(calset)} real flights)\n",
       "| real benign flights alarmed | sim thresholds | real-aware |", "|---|---|---|",
       f"| calibration split ({len(calset)}) | {fa(calset, h_sim, step_sim)} | {fa(calset, h_new, step_new)} (by construction) |",
       f"| **held-out** ({len(testset)}) | {fa(testset, h_sim, step_sim)} | **{fa(testset, h_new, step_new)}** |\n",
       "| attack-test2 (sim, GPS+IMU only), detected during attack | n | sim thresholds | real-aware |", "|---|---|---|---|"]
for (kind, rate), (n, a, b) in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    out.append(f"| {kind} {rate} | {n} | {a} | {b} |")
tot = [sum(v[i] for v in rows.values()) for i in range(3)]
out.append(f"| **total** | {tot[0]} | {tot[1]} | {tot[2]} |")
text = "\n".join(out)
Path("benchmarks/real-recal-v1.md").write_text(text + "\n", encoding="utf-8")
json.dump({"c3_h": h_new, "step_thresh_m": step_new, "calibrated_on": f"{len(calset)} real PX4 flights",
           "test_split": [p.name for p in testset]}, open("runs/real-recal.json", "w"), indent=1)
print(text.encode("ascii", "replace").decode())
