"""A5: parameter recovery on held-out attacks with known truth (attack-test2)."""
import collections, json, statistics as st
from pathlib import Path
import numpy as np
from astra import logs
from astra.detect import monitor
from astra.inversion import invert

cals = json.loads(Path("src/astra/data/a2-calibration.json").read_text())
cal = monitor.Calibration(**cals["gps+imu+flow"])
rows = []
for line in Path("runs/attack-test2/results.jsonl").read_text().splitlines():
    r = json.loads(line)
    npz = Path("runs/attack-test2") / f"{r['scenario_id']}__s0" / "flight.npz"
    if r["outcome"] == "error" or not npz.exists():
        continue
    fl = logs.load_npz(npz)
    inv = invert(fl, cal)
    if inv is None:
        continue
    sc = json.loads(json.dumps(r))  # truth from scenario id + log
    parts = r["scenario_id"].split("-")
    rate, ramp, kind = float(parts[-3][1:]), int(parts[-2][4:]), ("consistent" if parts[-1] == "c" else "naive")
    on_true = fl.attack_windows()[0][0]
    a = fl["ASTK"]; k = np.nonzero(a["Act"] > 0)[0][-1]
    brg_true = (np.degrees(np.arctan2(a["OfsE"][k], a["OfsN"][k]))) % 360
    berr = abs((inv.bearing_deg - brg_true + 180) % 360 - 180)
    rows.append({"rate": rate, "ramp": ramp, "kind": kind, "kind_ok": inv.kind == kind,
                 "rate_err": abs(inv.rate_ms - rate) / rate, "brg_err": berr, "onset_err": inv.onset_s - on_true})
g = collections.defaultdict(list)
for x in rows: g[(x["kind"], x["rate"])].append(x)
lines = ["# A5 incident inversion: parameter recovery (attack-test2, detected runs, bundled v7 calibration)\n",
         "| kind | true rate | runs | kind correct | rate error (median) | bearing error ° (median) | onset error s (median, + = late) |",
         "|---|---|---|---|---|---|---|"]
for (kind, rate), xs in sorted(g.items()):
    lines.append(f"| {kind} | {rate:g} m/s | {len(xs)} | {sum(x['kind_ok'] for x in xs)}/{len(xs)} | "
                 f"{100*st.median(x['rate_err'] for x in xs):.0f}% | {st.median(x['brg_err'] for x in xs):.0f} | "
                 f"{st.median(x['onset_err'] for x in xs):+.0f} |")
alle = rows
lines.append(f"\n**All {len(alle)} detected runs:** kind correct {sum(x['kind_ok'] for x in alle)}/{len(alle)}, median rate error "
             f"{100*st.median(x['rate_err'] for x in alle):.0f}%, median bearing error {st.median(x['brg_err'] for x in alle):.0f}°, "
             f"median onset error {st.median(x['onset_err'] for x in alle):+.0f} s")
text = "\n".join(lines); print(text); Path("benchmarks/a5-inversion-v1.md").write_text(text + "\n", encoding="utf-8")
