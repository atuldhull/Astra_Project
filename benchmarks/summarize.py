"""Summarise a results.jsonl into a per-scenario markdown table (errors listed, never dropped silently).

usage: python benchmarks/summarize.py RUN_DIR [--md OUT.md]
"""
import argparse
import collections
import json
import statistics as st
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("run_dir")
ap.add_argument("--md")
a = ap.parse_args()
rows = [json.loads(x) for x in (Path(a.run_dir) / "results.jsonl").read_text().splitlines()]
by = collections.defaultdict(list)
for r in rows:
    by[r["scenario_id"]].append(r)


def fmt(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


lines = ["| scenario | runs | outcomes | max nav err (m), median | L0 detected during attack | L0 latency (s), median | release-only |",
         "|---|---|---|---|---|---|---|"]
errors = []
for sid in sorted(by):
    rs = by[sid]
    ok = [r for r in rs if r["outcome"] != "error"]
    errors += [(sid, r["seed"], r["reason"]) for r in rs if r["outcome"] == "error"]
    oc = collections.Counter(r["outcome"] for r in rs)
    ws = [r["windows"][0] for r in ok if r.get("windows")]
    errs = [w["max_nav_error_m"] for w in ws if w["max_nav_error_m"] == w["max_nav_error_m"]]
    det = [w["l0_detected_during"] for w in ws]
    lat = [w["l0_detect_latency_s"] for w in ws if w["l0_detect_latency_s"] is not None]
    rel = [w["l0_release_only"] for w in ws]
    lines.append(
        f"| {sid} | {len(rs)} | {', '.join(f'{k}:{v}' for k, v in sorted(oc.items()))} | "
        f"{fmt(st.median(errs)) if errs else '-'} | "
        f"{f'{sum(det)}/{len(det)}' if ws else '-'} | {fmt(st.median(lat)) if lat else '-'} | "
        f"{f'{sum(rel)}/{len(rel)}' if ws else '-'} |")
text = "\n".join(lines)
if errors:
    text += "\n\n**Errored runs (excluded from metrics, listed for transparency):**\n" + "\n".join(
        f"- {s} seed {k}: {why}" for s, k, why in errors)
print(text)
if a.md:
    Path(a.md).write_text(text + "\n", encoding="utf-8")
