"""Qualification report: results bound to exact inputs, signed, ledgered, optionally timestamped.

Layout of a run directory:
  <out>/results.jsonl     per-run results (from astra.batch)
  <out>/report.json       signed envelope (kind="qualification-report")
  <out>/report.md         human-readable summary (not signed; regenerate from report.json)
"""

from __future__ import annotations

import collections
import json
import os
import shutil
import subprocess
from pathlib import Path

from astra import __version__
from astra.integrity.canonical import sha256_file, sha256_obj
from astra.integrity.ledger import Ledger
from astra.integrity.signing import Signer
from astra.scenario import Scenario
from astra.sitl import DEFAULT_IMAGE

REPO_ROOT = Path(__file__).resolve().parents[2]
PATCH = REPO_ROOT / "sim" / "ardupilot" / "astra-sitl-gps.patch"
PX4_PATCH = REPO_ROOT / "sim" / "px4" / "astra-px4-gps.patch"
PX4_IMAGE = "astra/px4-sitl:v1.17.0"


def astra_home() -> Path:
    return Path(os.environ.get("ASTRA_HOME") or Path.home() / ".astra")


def signer() -> Signer:
    return Signer.load_or_create(astra_home() / "keys" / "astra.ed25519")


def image_identity(image: str = DEFAULT_IMAGE, commit_file: str = "/opt/ardupilot/AP_COMMIT") -> dict:
    ident = {"image": image, "image_id": None, "ardupilot_commit": None}
    try:
        ident["image_id"] = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True, text=True, check=True).stdout.strip()
        ident["ardupilot_commit"] = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "cat", image, commit_file],
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    return ident


def _px4_identity() -> dict:
    ident = image_identity(PX4_IMAGE, "/src/PX4_COMMIT")
    ident["px4_commit"] = ident.pop("ardupilot_commit")
    return ident


def summarise(results: list[dict]) -> dict:
    by = collections.defaultdict(list)
    for r in results:
        by[r["scenario_id"]].append(r)
    per = {}
    for sid, rs in sorted(by.items()):
        valid = [r for r in rs if r["outcome"] != "error"]
        per[sid] = {
            "runs": len(rs),
            "errors": len(rs) - len(valid),
            "passed": sum(r["passed"] for r in valid),
            "outcomes": dict(collections.Counter(r["outcome"] for r in rs)),
            "stock_detected_during": sum(bool(r["windows"] and r["windows"][0].get("l0_detected_during"))
                                         for r in valid if r.get("windows")),
        }
    valid_runs = sum(p["runs"] - p["errors"] for p in per.values())
    return {
        "scenarios": len(per),
        "runs": sum(p["runs"] for p in per.values()),
        "errored_runs": sum(p["errors"] for p in per.values()),
        "passed_runs": sum(p["passed"] for p in per.values()),
        "pass_rate": round(sum(p["passed"] for p in per.values()) / valid_runs, 4) if valid_runs else None,
        "per_scenario": per,
    }


def build_body(pack_name: str, scenarios: list[Scenario], results: list[dict], *, seeds: int,
               speedup: int, vendor_param_file: Path | None, autopilot: str = "ardupilot") -> dict:
    slim = [{k: r[k] for k in ("scenario_id", "scenario_sha256", "seed", "outcome", "passed", "reason",
                               "metrics", "windows", "perturbation")} for r in results]
    return {
        "astra_version": __version__,
        "pack": {"name": pack_name, "scenario_sha256": {s.id: s.content_hash() for s in scenarios},
                 "pack_sha256": sha256_obj(sorted(s.content_hash() for s in scenarios))},
        "inputs": {
            "autopilot": autopilot,
            "simulator": (_px4_identity() if autopilot == "px4" else image_identity()),
            "simulator_patch_sha256": (sha256_file(PX4_PATCH) if autopilot == "px4" else sha256_file(PATCH))
            if (PX4_PATCH if autopilot == "px4" else PATCH).exists() else None,
            "vendor_params_sha256": sha256_file(vendor_param_file) if vendor_param_file else None,
            "vendor_params_file": vendor_param_file.name if vendor_param_file else "ardupilot-defaults",
            "seeds": seeds,
            "speedup": speedup,
        },
        "summary": summarise(results),
        "results": sorted(slim, key=lambda r: (r["scenario_id"], r["seed"])),
    }


def sign_and_record(out_dir: Path, body: dict, *, anchor: bool = False) -> dict:
    s = signer()
    env = s.sign("qualification-report", body)
    path = out_dir / "report.json"
    path.write_text(json.dumps(env, indent=1, sort_keys=True), encoding="ascii")
    report_sha = sha256_file(path)
    row = Ledger(astra_home() / "ledger.jsonl").append(
        "qualification-report", {"report_sha256": report_sha, "pack": body["pack"]["pack_sha256"],
                                 "signer": s.fingerprint})
    info = {"report": str(path), "report_sha256": report_sha, "signer_fingerprint": s.fingerprint,
            "ledger_seq": row["seq"], "ledger_hash": row["hash"], "anchored": False}
    if anchor:
        info["anchored"] = _ots_stamp(path)
    (out_dir / "report.md").write_text(render_md(env, info), encoding="utf-8")
    return info


def _ots_stamp(path: Path) -> bool:
    """OpenTimestamps (free, Bitcoin-anchored). Sends only the file's hash to public calendars."""
    ots = shutil.which("ots")
    if not ots:
        return False
    return subprocess.run([ots, "stamp", str(path)], capture_output=True).returncode == 0


def render_md(env: dict, info: dict | None = None) -> str:
    b = env["body"]
    s = b["summary"]
    lines = [
        f"# ASTRA qualification report: pack `{b['pack']['name']}`", "",
        f"- Pass rate: **{s['passed_runs']}/{s['runs'] - s['errored_runs']}** valid runs "
        f"({s['errored_runs']} errored, listed below, excluded)",
        f"- Simulator: `{b['inputs']['simulator']['image']}` (firmware commit "
        f"`{(b['inputs']['simulator'].get('ardupilot_commit') or b['inputs']['simulator'].get('px4_commit') or 'unknown')[:12]}`), patch sha256 "
        f"`{(b['inputs']['simulator_patch_sha256'] or '')[:12]}`",
        f"- Vendor params: `{b['inputs']['vendor_params_file']}` "
        f"(sha256 `{(b['inputs']['vendor_params_sha256'] or '-')[:12]}`)",
        f"- Seeds per scenario: {b['inputs']['seeds']}, speed-up {b['inputs']['speedup']}×",
        f"- Signed by key `{env['signer']['fingerprint'][:16]}…`", "",
        "| scenario | runs | passed | outcomes | stock autopilot detected attack during it |",
        "|---|---|---|---|---|",
    ]
    for sid, p in s["per_scenario"].items():
        lines.append(f"| {sid} | {p['runs']} | {p['passed']} | "
                     f"{', '.join(f'{k}:{v}' for k, v in sorted(p['outcomes'].items()))} | "
                     f"{p['stock_detected_during']}/{p['runs'] - p['errors']} |")
    errs = [r for r in b["results"] if r["outcome"] == "error"]
    if errs:
        lines += ["", "**Errored runs:**"] + [f"- {r['scenario_id']} seed {r['seed']}: {r['reason']}" for r in errs]
    if info:
        lines += ["", f"Report sha256 `{info['report_sha256']}`; ledger seq {info['ledger_seq']}; "
                      f"externally anchored: {info['anchored']}.",
                  "", "Verify: `astra verify report.json --trust <fingerprint>`"]
    return "\n".join(lines) + "\n"
