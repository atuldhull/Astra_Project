"""ASTRA Shield (onboard C3 Lua monitor): calibrate on its own logged residuals, then test.

phase "fly":   fly benign-v1[:N] (calibration), benign-v2 (held-out FAR) and attack-test with the
               monitor in log-only mode.
phase "eval":  calibrate Σ/k/h on benign-v1 ASTM blocks only; replay the onboard CUSUM arithmetic
               on held-out logs; report FAR + detection; write the armed Lua script.
phase "verify": fly a few attacks with the ARMED script and check the onboard alarm time matches
               the offline replay of the same flight.

usage: python benchmarks/shield_eval.py fly|eval|verify OUT_DIR [--ncal 40] [--parallel 6]
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics as st
from pathlib import Path

import numpy as np

from astra import logs
from astra.batch import run_batch
from astra.evaluate import nav_error_series
from astra.onboard import lua_monitor
from astra.packs import PACKS

DELTA = 1.0
K = 2.0 + DELTA ** 2 / 2


def cusum(q):
    s, S = 0.0, []
    for v in q:
        s = max(0.0, s + min(v, 100.0) - K)
        S.append(s)
    return np.asarray(S)


def astm(npz: Path):
    fl = logs.load_npz(npz)
    a = fl["ASTM"] if fl.has("ASTM") else None
    return fl, a


def fly(out: Path, ncal: int, parallel: int):
    script = {"astra_shield.lua": lua_monitor(None)}
    sets = [("cal", PACKS["benign-v1"]()[:ncal]), ("far", PACKS["benign-v2"]()), ("atk", PACKS["attack-test"]())]
    for name, scs in sets:
        r = run_batch([(s, 0) for s in scs], out / name, parallel=parallel, speedup=20, extra_scripts=script)
        print(name, json.dumps(r["summary"]), flush=True)


def _blocks(d: Path):
    out = []
    for line in (d / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        npz = d / f"{r['scenario_id']}__s{r['seed']}" / "flight.npz"
        if r["outcome"] == "error" or not npz.exists():
            continue
        fl, a = astm(npz)
        if a is None or len(a["t"]) < 5:
            continue
        out.append((r, fl, a))
    return out


def evaluate(out: Path):
    cal_runs = _blocks(out / "cal")
    R = np.concatenate([np.stack([a["rN"], a["rE"]], 1) for _, _, a in cal_runs])
    sinv = np.linalg.inv(np.cov(R.T) + 1e-9 * np.eye(2))

    def q_of(a):
        r = np.stack([a["rN"], a["rE"]], 1)
        return np.einsum("ni,ij,nj->n", r, sinv, r)

    h = 1.25 * max(cusum(q_of(a)).max() for _, _, a in cal_runs)
    cal = {"sigma_inv": sinv.tolist(), "k": K, "h": float(h), "n_cal_flights": len(cal_runs),
           "cal_hours": float(sum((a["t"][-1] - a["t"][0]) for _, _, a in cal_runs) / 3600)}
    far_runs = _blocks(out / "far")
    far_hours = sum((a["t"][-1] - a["t"][0]) for _, _, a in far_runs) / 3600
    fa = sum(bool((cusum(q_of(a)) > h).any()) for _, _, a in far_runs)
    groups = collections.defaultdict(list)
    for r, fl, a in _blocks(out / "atk"):
        on = fl.attack_windows()[0][0]
        S = cusum(q_of(a))
        idx = np.nonzero(S > h)[0]
        t_al = float(a["t"][idx[0]]) if len(idx) else None
        hit = t_al is not None and t_al >= on
        te, err = nav_error_series(fl)
        parts = r["scenario_id"].split("-")
        groups[(parts[-3], parts[-2], parts[-1])].append(
            {"hit": hit, "pre": t_al is not None and t_al < on, "lat": t_al - on if hit else None,
             "err": float(np.interp(t_al, te, err)) if hit else None})
    from scipy.stats import chi2
    ub = chi2.ppf(0.975, 2 * (fa + 1)) / 2 / far_hours
    lines = ["# ASTRA Shield (onboard C3, Lua) evaluation\n",
             f"calibration: {cal['n_cal_flights']} benign-v1 flights ({cal['cal_hours']:.2f} h of airborne blocks); h={h:.1f}, k={K}\n",
             f"held-out benign-v2: **{fa} alarmed flights in {far_hours:.2f} h** (95% upper bound {ub:.2f}/h)\n",
             "| rate | ramp | velocity | runs | Shield detected | latency s (median) | error at alarm m (median) | pre-onset |",
             "|---|---|---|---|---|---|---|---|"]
    tot = collections.Counter()
    for key in sorted(groups, key=lambda k: (float(k[0][1:]), int(k[1][4:]), k[2])):
        g = groups[key]
        lat = [x["lat"] for x in g if x["lat"] is not None]
        err = [x["err"] for x in g if x["err"] is not None]
        tot["n"] += len(g); tot["hit"] += sum(x["hit"] for x in g)
        lines.append(f"| {key[0][1:]} | {key[1][4:]} | {'consistent' if key[2] == 'c' else 'naive'} | {len(g)} | "
                     f"{sum(x['hit'] for x in g)}/{len(g)} | {st.median(lat):.1f} | {st.median(err):.1f} | "
                     f"{sum(x['pre'] for x in g)} |" if lat else
                     f"| {key[0][1:]} | {key[1][4:]} | {'consistent' if key[2] == 'c' else 'naive'} | {len(g)} | 0/{len(g)} | - | - | {sum(x['pre'] for x in g)} |")
    lines.append(f"\n**Total:** {tot['hit']}/{tot['n']}\n")
    text = "\n".join(lines)
    print(text)
    (Path("benchmarks") / "shield-v1.md").write_text(text, encoding="utf-8")
    (out / "shield_cal.json").write_text(json.dumps(cal, indent=1))
    Path("src/astra/data/astra_shield.lua").write_text(lua_monitor(cal), encoding="ascii", newline="\n")


def verify(out: Path, parallel: int):
    cal = json.loads((out / "shield_cal.json").read_text())
    scs = [s for s in PACKS["attack-test"]() if s.id.endswith("-n") and ("-r1-" in s.id or "-r2-" in s.id)][:6]
    res = run_batch([(s, 0) for s in scs], out / "verify", parallel=parallel, speedup=20,
                    extra_scripts={"astra_shield.lua": lua_monitor(cal)})
    sinv = np.asarray(cal["sigma_inv"])
    for r in res["results"]:
        fl, a = astm(out / "verify" / f"{r.scenario_id}__s0" / "flight.npz")
        onboard = next((t for t, m in fl.messages if "ASTRA Shield: GNSS" in m), None)
        rr = np.stack([a["rN"], a["rE"]], 1)
        q = np.einsum("ni,ij,nj->n", rr, sinv, rr)
        S = cusum(q)
        idx = np.nonzero(S > cal["h"])[0]
        offline = float(a["t"][idx[0]]) if len(idx) else None
        print(f"{r.scenario_id}: onboard alarm t={onboard}  offline replay t={offline}  outcome={r.outcome}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["fly", "eval", "verify"]); ap.add_argument("out")
    ap.add_argument("--ncal", type=int, default=40); ap.add_argument("--parallel", type=int, default=6)
    a = ap.parse_args()
    {"fly": lambda: fly(Path(a.out), a.ncal, a.parallel), "eval": lambda: evaluate(Path(a.out)),
     "verify": lambda: verify(Path(a.out), a.parallel)}[a.phase]()
