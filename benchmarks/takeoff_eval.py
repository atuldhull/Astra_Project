"""Power-on spoofing check (`diagnose --takeoff`): false-alarm rate on simulated benign flights.

Declared pad = the simulator's true take-off point. A spoof present from boot that shifts the GPS by D
metres is caught iff the measured offset exceeds the limit, so the benign offset distribution gives both
the false-alarm rate and the smallest detectable boot-time offset.
usage: python benchmarks/takeoff_eval.py OUT.md GLOB [GLOB ...]
"""
import glob, sys, warnings
from pathlib import Path
import numpy as np
from astra import logs
from astra.forensics import takeoff_check

warnings.filterwarnings("ignore")
out, pats = sys.argv[1], sys.argv[2:]
lines = ["# Power-on spoofing check (take-off point vs declared pad), simulated benign flights\n",
         "Declared pad = simulator truth, radius 15 m. Limit = 15 m + max(10 m, 3 x reported accuracy).\n",
         "| set | flights | offset p50 / p95 / max (m) | limit p50 (m) | false alarms |", "|---|---|---|---|---|"]
for pat in pats:
    offs, lims, fa = [], [], 0
    for p in sorted(glob.glob(pat, recursive=True)):
        fl = logs.load_npz(Path(p))
        if not fl.has("SIM"):
            continue
        s = fl["SIM"]
        r = takeoff_check(fl, float(s["Lat"][0]), float(s["Lng"][0]))
        if r is None:
            continue
        offs.append(r["offset_m"]); lims.append(r["limit_m"]); fa += r["mismatch"]
    if offs:
        o = np.array(offs)
        lines.append(f"| `{pat}` | {len(o)} | {np.percentile(o,50):.1f} / {np.percentile(o,95):.1f} / {o.max():.1f} "
                     f"| {np.median(lims):.1f} | {fa}/{len(o)} |")
Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
