"""C5 (displacement) scored on data never used to design it: benign-v3 + attack-test2 + 39 real PX4 flights."""
import collections, json, statistics as st
from pathlib import Path
import numpy as np
from astra import logs
from astra.detect import displacement as c5
from astra.evaluate import nav_error_series
from astra.ulog import load_ulog

def runs(d):
    for l in open(f"{d}/results.jsonl"):
        r = json.loads(l); p = Path(d) / f"{r['scenario_id']}__s{r['seed']}" / "flight.npz"
        if r["outcome"] != "error" and p.exists(): yield r, logs.load_npz(p)

cal = c5.calibrate([fl for _, fl in runs("runs/benign-v1")])   # all 160 benign-v1 (design corpus)
fa_b = [c5.first_alarm(fl, cal) is not None for _, fl in runs("runs/benign-v3")]
H_b = sum(len(c5.displacement_series(fl)[0]) for _, fl in runs("runs/benign-v3")) * 0.2 / 3600
real = [load_ulog(p) for p in sorted(Path("runs/px4real").glob("*.ulg"))]
fa_r = [c5.first_alarm(fl, cal) is not None for fl in real]
g = collections.defaultdict(list)
for r, fl in runs("runs/attack-test2"):
    if not r["scenario_id"].endswith("-n"): continue
    on = fl.attack_windows()[0][0]; t = c5.first_alarm(fl, cal); hit = t is not None and t >= on
    te, err = nav_error_series(fl)
    w = r["windows"][0] if r.get("windows") else {}
    g[r["scenario_id"].split("-")[-3]].append((hit, float(np.interp(t, te, err)) if hit else None, t is not None and t < on))
lines = ["# C5 long-window displacement test (W = 60 s) — scored on data never used to design it\n",
         f"threshold {cal['threshold_m']:.2f} m (1.25 × worst of {cal['n_flights']} benign-v1 flights)",
         f"- held-out simulated benign (benign-v3): **{sum(fa_b)}/{len(fa_b)} flights alarmed** (~{H_b:.1f} h)",
         f"- **real PX4 benign flights: {sum(fa_r)}/{len(fa_r)} alarmed** (real-flight gate)\n",
         "| naive drag rate | detected | error at alarm m (median) | pre-onset |", "|---|---|---|---|"]
for rate in sorted(g, key=lambda x: float(x[1:])):
    xs = g[rate]; hits = [e for ok, e, _ in xs if ok]
    lines.append(f"| {rate[1:]} m/s | {len(hits)}/{len(xs)} | {st.median(hits):.0f} | {sum(p for *_, p in xs)} |" if hits else f"| {rate[1:]} m/s | 0/{len(xs)} | - | {sum(p for *_, p in xs)} |")
text = "\n".join(lines); print(text); Path("benchmarks/c5-displacement-v1.md").write_text(text + "\n", encoding="utf-8")
json.dump(cal, open("runs/c5-cal.json", "w"))
