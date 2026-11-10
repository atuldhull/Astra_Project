"""A2 monitor evaluation: calibrate on benign-train, measure FAR on benign-test, detection on attacks.

usage: python benchmarks/a2_eval.py BENIGN_DIR ATTACK_DIR [--out benchmarks/a2-<name>.md] [--save-cal FILE]

Honesty rules enforced here:
  * calibration (flow model, covariances, thresholds) uses benign-train only
  * FAR is reported on benign-test with a Poisson 95% upper bound
  * an alarm before attack onset in an attack run counts as a false alarm, not a detection
  * results are grouped so weak cases are visible, not averaged away
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

from astra import logs
from astra.detect import features, monitor
from astra.evaluate import nav_error_series

CONFIGS = {"gps+imu": ["c1", "c3"], "gps+imu+flow": ["c1", "c2", "c3"]}


def load_runs(d: Path):
    out = []
    for line in (d / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        npz = d / f"{r['scenario_id']}__s{r['seed']}" / "flight.npz"
        if r["outcome"] == "error" or not npz.exists():
            continue
        out.append((r, npz))
    return out


def apply_flow(ch, M, B=None):
    return features.apply_flow(ch, M, B)


def poisson_upper95(k: int, hours: float) -> float:
    from scipy.stats import chi2
    return chi2.ppf(0.975, 2 * (k + 1)) / 2 / hours if hours > 0 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("benign"); ap.add_argument("attack")
    ap.add_argument("--out"); ap.add_argument("--save-cal")
    ap.add_argument("--benign-test", help="separate held-out benign dir: calibrate on ALL of BENIGN_DIR, test FAR here")
    a = ap.parse_args()

    benign = load_runs(Path(a.benign))
    chs = []
    for r, npz in benign:
        try:
            chs.append((r, features.compute(logs.load_npz(npz))))
        except ValueError as exc:
            print("skip", r["scenario_id"], exc, file=sys.stderr)
    if a.benign_test:
        train = [c for _, c in chs]
        test = []
        for r, npz in load_runs(Path(a.benign_test)):
            try:
                test.append(features.compute(logs.load_npz(npz)))
            except ValueError as exc:
                print("skip", r["scenario_id"], exc, file=sys.stderr)
    else:
        train = [c for i, (_, c) in enumerate(chs) if i % 2 == 0]
        test = [c for i, (_, c) in enumerate(chs) if i % 2 == 1]
    M = features.fit_flow_model(train)
    for c in train:
        apply_flow(c, M)
    B = features.fit_flow_nuisance(train)
    for c in train + test:
        apply_flow(c, M, B)

    lines = [f"# A2 monitor evaluation\n", f"benign flights: {len(train)} calibration / {len(test)} held-out test\n",
             f"flow model (fitted on calibration only): {np.round(M, 3).tolist()}\n"]
    cals = {}
    for cfg, chans in CONFIGS.items():
        cal = monitor.calibrate(train, chans)
        cal.flow_model = M.tolist()
        cal.flow_nuisance = B.tolist()
        cals[cfg] = cal
        fa, hours, by = 0, 0.0, collections.Counter()
        for c in test:
            hours += float(c.airborne.sum()) * features.DT / 3600
            det, _ = monitor.run(c, cal, chans)
            if det.alarm:
                fa += 1
                by[det.channel] += 1
        lines.append(f"\n## {cfg}: false alarms on held-out benign\n")
        lines.append(f"- {fa} alarmed flights in {hours:.2f} airborne hours "
                     f"(rate {fa / hours:.2f}/h, 95% upper bound {poisson_upper95(fa, hours):.2f}/h); by channel {dict(by)}\n")
        lines.append(f"- thresholds h: { {k: round(v, 1) for k, v in cal.h.items()} }  (calibration hours {cal.airborne_hours:.2f})\n")

    # attacks
    attacks = load_runs(Path(a.attack))
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for r, npz in attacks:
        fl = logs.load_npz(npz)
        wins = fl.attack_windows()
        if not wins:
            continue
        onset = wins[0][0]
        try:
            ch = apply_flow(features.compute(fl), M, B)
        except ValueError:
            continue
        te, err = nav_error_series(fl)
        w0 = r["windows"][0] if r.get("windows") else {}
        sid = r["scenario_id"]
        parts = sid.split("-")
        key = (parts[-3], parts[-2], parts[-1])  # rate, ramp, c/n
        for cfg, chans in CONFIGS.items():
            det, _ = monitor.run(ch, cals[cfg], chans)
            pre = det.alarm and det.t_alarm < onset
            hit = det.alarm and not pre
            lat = det.t_alarm - onset if hit else None
            e_at = float(np.interp(det.t_alarm, te, err)) if hit else None
            groups[cfg][key].append({"hit": hit, "pre": pre, "lat": lat, "err": e_at, "ch": det.channel,
                                     "final_err": float(err[-1]), "outcome": r["outcome"],
                                     "l0": bool(w0.get("l0_detected_during")), "l0_lat": w0.get("l0_detect_latency_s")})

    def med(x):
        x = [v for v in x if v is not None]
        return f"{st.median(x):.1f}" if x else "-"

    for cfg in CONFIGS:
        lines.append(f"\n## {cfg}: drag-off detection ({Path(a.attack).name})\n")
        lines.append("| rate | ramp | velocity | runs | stock L0 detected | A2 detected | A2 latency s (median) | error at A2 alarm m (median) | pre-onset alarms | channel |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        tot = collections.Counter()
        for key in sorted(groups[cfg], key=lambda k: (float(k[0][1:]), int(k[1][4:]), k[2])):
            g = groups[cfg][key]
            n = len(g)
            hits = sum(x["hit"] for x in g)
            l0 = sum(x["l0"] for x in g)
            tot["n"] += n; tot["hit"] += hits; tot["l0"] += l0; tot["pre"] += sum(x["pre"] for x in g)
            chs_ = collections.Counter(x["ch"] for x in g if x["hit"])
            lines.append(f"| {key[0][1:]} m/s | {key[1][4:]} s | {'consistent' if key[2]=='c' else 'naive'} | {n} | {l0}/{n} | {hits}/{n} | "
                         f"{med([x['lat'] for x in g])} | {med([x['err'] for x in g])} | {sum(x['pre'] for x in g)} | {dict(chs_)} |")
        lines.append(f"\n**Total:** stock {tot['l0']}/{tot['n']} vs A2 {tot['hit']}/{tot['n']} (pre-onset alarms: {tot['pre']})\n")
    text = "\n".join(lines)
    print(text)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    if a.save_cal:
        Path(a.save_cal).write_text(json.dumps({k: json.loads(v.to_json()) for k, v in cals.items()}, indent=2))


if __name__ == "__main__":
    main()
