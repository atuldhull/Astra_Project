"""Real-flight gate v3: score the FROZEN `astra diagnose` (with real_gate settings) once on fresh public
PX4 flights (runs/px4real3, selected with seed "astra-real-v3", never used in design).

Verdicts on benign real flights: 'spoofing-like' / 'mixed' = false accusation; 'jamming-like' = receiver
reported fix/satellite loss (reported separately, it reflects the receiver's own status);
'inconclusive' = weak evidence (counted, not an accusation).
"""
import collections, json, warnings
from pathlib import Path
from scipy.stats import chi2
from astra.forensics import diagnose
from astra.ulog import load_ulog
from astra.detect import features

warnings.filterwarnings("ignore")
cnt, names, H, skipped = collections.Counter(), collections.defaultdict(list), 0.0, []
import sys
SRC, OUT = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("runs/px4real3", "benchmarks/real-gate-v3.md")
for p in sorted(Path(SRC).glob("*.ulg")):
    try:
        fl = load_ulog(p)
        h = float(features.compute(fl).airborne.sum()) * features.DT / 3600
        if h < 0.02:
            skipped.append((p.name[:8], "under 72 s airborne")); continue
        v = diagnose(p)["verdict"].split(":")[0].split(" ")[0]
    except Exception as exc:  # noqa: BLE001
        skipped.append((p.name[:8], f"{type(exc).__name__}: {str(exc)[:60]}")); continue
    H += h; cnt[v] += 1; names[v].append(p.name[:8])
n = sum(cnt.values())
acc = cnt["spoofing-like"] + cnt["mixed"]
DESIGN = sys.argv[3] if len(sys.argv) > 3 else "159 other flights (real-far-v2.md)"
lines = [f"# Real-flight gate ({SRC}: fresh public PX4 flights, frozen `astra diagnose`)\n",
         f"{n} usable flights, {H:.1f} airborne h; {len(skipped)} unusable. Design set: {DESIGN}. Scored once.\n",
         "| verdict on real benign flight | flights |", "|---|---|"]
for k in ("no", "not", "inconclusive", "jamming-like", "RF-attack-like", "spoofing-like", "mixed"):
    lines.append(f"| {k if k != 'no' else 'no anomaly'} | {cnt[k]} |")
lines.append(f"\n**False spoofing accusations: {acc}/{n}** (95% upper bound "
             f"{chi2.ppf(0.975, 2 * (acc + 1)) / 2 / n * 100:.1f}% of flights).")
for k in ("spoofing-like", "mixed", "RF-attack-like", "inconclusive", "jamming-like"):
    if names[k]:
        lines.append(f"- {k}: {', '.join(names[k])}")
if skipped:
    lines += ["\nUnusable logs:"] + [f"- {a}: {b}" for a, b in skipped]
text = "\n".join(lines)
Path(OUT).write_text(text + "\n", encoding="utf-8")
print(text.encode("ascii", "replace").decode())
