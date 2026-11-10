"""A3: score `astra diagnose` verdicts against ground truth.

Classes: jamming (jam_* models), spoofing (spoof_drag, spoof_jump, meaconing), none (benign).
Verdict mapping: "jamming-like" → jamming, "spoofing-like" → spoofing, "mixed" → counted separately,
"no GNSS anomaly" → none.

usage: python benchmarks/a3_eval.py DIR [DIR ...] --out benchmarks/a3-v1.md
"""
from __future__ import annotations

import argparse
import collections
import json
import warnings
from pathlib import Path

from astra.forensics import diagnose

warnings.filterwarnings("ignore")
JAM = {"jam_denial", "jam_intermittent", "jam_chaotic", "jam_degrade"}


def truth(rep: dict) -> tuple[str, str]:
    gt = rep.get("ground_truth") or []
    if not gt:
        return "none", "benign"
    m = gt[0]["model"]
    return ("jamming" if m in JAM else "spoofing"), m


def verdict(rep: dict) -> str:
    v = rep["verdict"]
    if v.startswith("jamming-like"):
        return "jamming"
    if v.startswith("spoofing-like"):
        return "spoofing"
    if v.startswith("mixed"):
        return "mixed"
    return "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+"); ap.add_argument("--out")
    a = ap.parse_args()
    conf = collections.Counter()
    by_model = collections.defaultdict(collections.Counter)
    for d in a.dirs:
        for line in (Path(d) / "results.jsonl").read_text().splitlines():
            r = json.loads(line)
            npz = Path(d) / f"{r['scenario_id']}__s{r['seed']}" / "flight.npz"
            if r["outcome"] == "error" or not npz.exists():
                continue
            rep = diagnose(npz)
            t, model = truth(rep)
            v = verdict(rep)
            if model == "spoof_drag":
                rate = r["scenario_id"].split("-")[-3]
                model = f"spoof_drag {rate[1:]} m/s"
            conf[t, v] += 1
            by_model[model][v] += 1
    classes, verdicts = ["jamming", "spoofing", "none"], ["jamming", "spoofing", "mixed", "none"]
    lines = ["# A3: forensics verdict accuracy (`astra diagnose`, bundled A2 v7 calibration)\n",
             "Confusion (rows = truth, columns = verdict):\n",
             "| truth \\ verdict | " + " | ".join(verdicts) + " | correct |", "|---|" + "---|" * (len(verdicts) + 1)]
    for t in classes:
        n = sum(conf[t, v] for v in verdicts)
        lines.append(f"| {t} | " + " | ".join(str(conf[t, v]) for v in verdicts) + f" | {conf[t, t]}/{n} |")
    lines += ["\nBy attack model:\n", "| model | " + " | ".join(verdicts) + " |", "|---|" + "---|" * len(verdicts)]
    for m in sorted(by_model):
        lines.append(f"| {m} | " + " | ".join(str(by_model[m][v]) for v in verdicts) + " |")
    text = "\n".join(lines)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
