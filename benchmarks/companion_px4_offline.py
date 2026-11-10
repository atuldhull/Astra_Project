"""Shield(-Companion) on PX4, evaluated offline from existing PX4 SITL logs via the verified mirror.

Calibrate on px4-benign-cal (80), FAR on px4-benign (40, held-out), detection on px4-attack-naive (48).
"""
import collections, json, statistics as st
from pathlib import Path
import numpy as np
from astra import logs
from astra.evaluate import nav_error_series
from astra.onboard import calibrate_from_logs, replay_cusum, shield_blocks

def runs(d):
    for line in (Path(d) / "results.jsonl").read_text().splitlines():
        r = json.loads(line); npz = Path(d) / f"{r['scenario_id']}__s{r['seed']}" / "flight.npz"
        if r["outcome"] != "error" and npz.exists():
            yield r, npz

cal, info = calibrate_from_logs([str(n) for _, n in runs("runs/px4-benign-cal")])
S, h = np.asarray(cal["sigma_inv"]), cal["h"]
def alarm(fl):
    T, B = shield_blocks(fl)
    if not len(B): return None
    Sc = replay_cusum(np.einsum("ni,ij,nj->n", B, S, B)); i = np.nonzero(Sc > h)[0]
    return float(T[i[0]]) if len(i) else None
H = fa = 0
for r, n in runs("runs/px4-benign"):
    fl = logs.load_npz(n); T, B = shield_blocks(fl); H += len(B) * 4 / 3600; fa += alarm(fl) is not None
g = collections.defaultdict(list)
for r, n in runs("runs/px4-attack-naive"):
    fl = logs.load_npz(n); on = fl.attack_windows()[0][0]; t = alarm(fl)
    te, err = nav_error_series(fl); rate = r["scenario_id"].split("-")[-3]
    g[rate].append((t is not None and t >= on, None if t is None or t < on else float(np.interp(t, te, err))))
lines = ["# Shield-Companion on PX4 (offline replay via the verified mirror)\n",
         f"calibration: {info['flights']} PX4 benign flights ({info['airborne_hours']:.2f} h); h={h:.1f}",
         f"held-out PX4 benign: **{fa} alarmed flights in {H:.2f} h**\n",
         "| drag rate (naive) | detected | error at alarm m (median) |", "|---|---|---|"]
tot = [0, 0]
for rate in sorted(g, key=lambda x: float(x[1:])):
    hits = [e for ok, e in g[rate] if ok]; tot[0] += len(hits); tot[1] += len(g[rate])
    lines.append(f"| {rate[1:]} m/s | {len(hits)}/{len(g[rate])} | {st.median(hits):.1f} |" if hits else f"| {rate[1:]} m/s | 0/{len(g[rate])} | - |")
lines.append(f"\n**Total:** {tot[0]}/{tot[1]} (stock PX4 on the same flights: 10/48)")
text = "\n".join(lines); print(text); Path("benchmarks/companion-px4-v1.md").write_text(text + "\n", encoding="utf-8")
Path("runs/px4-shield-cal.json").write_text(json.dumps(cal, indent=1))
