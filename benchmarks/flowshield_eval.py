"""Flow-Shield (companion C2) evaluation, calibrated on its OWN live residuals.

phase 1  collect: fly benign-v1[:40] with Flow-Shield in collection mode (h = inf)
phase 2  calibrate: Σ from the collected block residuals; h = 1.25 × max replayed CUSUM peak
phase 3  test (armed, live): FAR on benign-v3[6:46]; detection on attack-test2 consistent drag-offs (48)
"""
import collections, json, statistics as st
from pathlib import Path
import numpy as np
from astra.batch import run_batch
from astra.packs import PACKS
from astra.evaluate import nav_error_series
from astra import logs

OUT = Path("runs/flowshield-eval")
base = json.loads(Path("src/astra/data/a2-calibration.json").read_text())["gps+imu+flow"]


def cusum(q, k):
    s, S = 0.0, []
    for v in q:
        s = max(0.0, s + min(v, 100.0) - k); S.append(s)
    return np.asarray(S)


# 1) collect
collect = dict(base); collect["h"] = {**base["h"], "c2": float("inf")}
res = run_batch([(s, 0) for s in PACKS["benign-v1"]()[:40]], OUT / "collect", parallel=6, speedup=20,
                **{})  if False else None
from astra.runner import fly
from concurrent.futures import ThreadPoolExecutor

def flyc(s, sub, cal):
    return fly(s, 0, OUT / sub / f"{s.id}__s0", speedup=20, companion={"flow_cal": cal})

with ThreadPoolExecutor(6) as ex:
    col = list(ex.map(lambda s: flyc(s, "collect", collect), PACKS["benign-v1"]()[:40]))
raws = [np.array([[b, c] for _, b, c in r.metrics.get("companion", {}).get("flow_raw", [])]) for r in col]
raws = [x for x in raws if len(x) >= 5]
R = np.concatenate(raws)
sinv = np.linalg.inv(np.cov(R.T) + 1e-9 * np.eye(2))
k = float(base["k"]["c2"])
q = lambda x: np.einsum("ni,ij,nj->n", x, sinv, x)
h = 1.25 * max(cusum(q(x), k).max() for x in raws)
armed = dict(base); armed["sigma_inv"] = {**base["sigma_inv"], "c2": sinv.tolist()}; armed["h"] = {**base["h"], "c2": float(h)}
hours_cal = sum(len(x) for x in raws) * 4 / 3600

# 3) test
with ThreadPoolExecutor(6) as ex:
    ben = list(ex.map(lambda s: flyc(s, "benign", armed), PACKS["benign-v3"]()[6:46]))
    atk = list(ex.map(lambda s: flyc(s, "attack", armed), [s for s in PACKS["attack-test2"]() if s.id.endswith("-c")]))
bok = [r for r in ben if r.outcome != "error" and r.metrics.get("companion", {}).get("flow_raw")]
fa = sum(r.metrics["companion"].get("flow_alarm_boot_t") is not None for r in bok)
H = sum(len(r.metrics["companion"]["flow_raw"]) for r in bok) * 4 / 3600
g = collections.defaultdict(list)
for r in atk:
    if r.outcome == "error":
        continue
    fl = logs.load_npz(OUT / "attack" / f"{r.scenario_id}__s0" / "flight.npz")
    on = fl.attack_windows()[0][0]
    t = r.metrics.get("companion", {}).get("flow_alarm_boot_t")
    hit = t is not None and t >= on
    te, err = nav_error_series(fl)
    g[r.scenario_id.split("-")[-3]].append((hit, float(np.interp(t, te, err)) if hit else None, t is not None and t < on))
from scipy.stats import chi2
lines = ["# Flow-Shield (companion, optical-flow witness), calibrated on its own live residuals\n",
         f"calibration: {len(raws)} benign flights, {hours_cal:.2f} h of live blocks; h = {h:.1f}",
         f"held-out benign (live, armed): **{fa} alarms in {H:.2f} h** over {len(bok)} flights "
         f"(95% UB {chi2.ppf(0.975, 2 * (fa + 1)) / 2 / H:.2f}/h)\n",
         "| consistent drag rate | detected | error at alarm m (median) | pre-onset alarms |", "|---|---|---|---|"]
tot = [0, 0]
for rate in sorted(g, key=lambda x: float(x[1:])):
    xs = g[rate]; hits = [e for ok, e, _ in xs if ok]; tot[0] += len(hits); tot[1] += len(xs)
    lines.append(f"| {rate[1:]} m/s | {len(hits)}/{len(xs)} | {st.median(hits):.0f} | {sum(p for *_, p in xs)} |" if hits
                 else f"| {rate[1:]} m/s | 0/{len(xs)} | - | {sum(p for *_, p in xs)} |")
lines.append(f"\n**Total:** {tot[0]}/{tot[1]} consistent drag-offs (stock autopilot on these flights: 0)")
text = "\n".join(lines); print(text)
Path("benchmarks/flowshield-v1.md").write_text(text + "\n", encoding="utf-8")
Path("runs/flowshield-cal.json").write_text(json.dumps(armed, indent=1))
