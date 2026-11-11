"""astra: command-line interface.

  astra packs                              list built-in scenario packs
  astra run PACK --out DIR [options]       fly a pack, write signed report
  astra verify REPORT --trust FP           verify a signed report (offline)
  astra key                                show this installation's signing fingerprint
  astra ledger verify                      re-walk the local hash-chained ledger
  astra diagnose LOG.BIN|flight.npz        forensics on a flight log (A2 monitor)
  astra calibrate LOGS... --out CAL.json   airframe-specific A2 calibration from benign logs
  astra shield calibrate|export ...        onboard Lua monitor (log-only -> calibrate -> armed)
  astra advise --params P.parm --out DIR   measured EKF-tuning trade-off (A6)
  astra html RUN_DIR                       self-contained HTML report
  astra invert LOG [--mission M.yaml]      estimate the attack and emit a reproducible scenario (A5)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_packs(a):
    from astra.packs import PACKS
    for name, fn in sorted(PACKS.items()):
        scs = fn()
        print(f"{name:14s} {len(scs):4d} scenarios")


def _cmd_run(a):
    from astra.batch import run_batch
    from astra.packs import PACKS
    from astra.report import build_body, sign_and_record

    if a.pack not in PACKS:
        sys.exit(f"unknown pack {a.pack!r}; see `astra packs`")
    scs = [s for s in PACKS[a.pack]() if a.only in s.id]
    jobs = [(s, k) for s in scs for k in range(a.seeds)]
    out = Path(a.out)
    vend = Path(a.params) if a.params else None
    print(f"{len(jobs)} runs ({len(scs)} scenarios × {a.seeds} seeds), parallel={a.parallel or 'auto'}, "
          f"speed-up {a.speedup}×", flush=True)
    n = [0]

    def tick(r):
        n[0] += 1
        print(f"  [{n[0]}/{len(jobs)}] {r.scenario_id} s{r.seed}: {r.outcome} ({r.reason})", flush=True)

    res = run_batch(jobs, out, parallel=a.parallel, speedup=a.speedup, vendor_param_file=vend, on_result=tick,
                    autopilot=a.autopilot)
    results = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
    body = build_body(a.pack, scs, results, seeds=a.seeds, speedup=a.speedup, vendor_param_file=vend,
                      autopilot=a.autopilot)
    info = sign_and_record(out, body, anchor=a.anchor)
    print(json.dumps(res["summary"]))
    print(f"report: {info['report']}  signer: {info['signer_fingerprint']}  anchored: {info['anchored']}")


def _cmd_verify(a):
    from astra.integrity.signing import verify
    env = json.loads(Path(a.report).read_text())
    trusted = list(a.trust or [])
    if a.trust_file:
        trusted += [x.strip() for x in Path(a.trust_file).read_text().splitlines() if x.strip()]
    r = verify(env, trusted)
    print(json.dumps({"valid_signature": r.valid, "trusted_signer": r.trusted,
                      "fingerprint": r.fingerprint, "reason": r.reason}, indent=1))
    sys.exit(0 if r.ok else 1)


def _cmd_key(a):
    from astra.report import astra_home, signer
    s = signer()
    print(s.fingerprint)
    print(f"(key file: {astra_home() / 'keys' / 'astra.ed25519'}; share only the fingerprint)", file=sys.stderr)


def _cmd_ledger(a):
    from astra.integrity.ledger import Ledger
    from astra.report import astra_home
    c = Ledger(astra_home() / "ledger.jsonl").verify()
    print(json.dumps(c.__dict__, indent=1))
    sys.exit(0 if c.ok else 1)


def _cmd_diagnose(a):
    from astra.forensics import diagnose
    tk = tuple(float(x) for x in a.takeoff.split(",")) if a.takeoff else None
    rep = diagnose(Path(a.log), cal_file=Path(a.cal) if a.cal else None, takeoff=tk)
    if a.html:
        from astra.forensics_html import render
        print(f"verdict: {rep['verdict']}\nreport:  {render(rep, Path(a.html))}")
    else:
        print(json.dumps(rep, indent=1, default=str))


def _cmd_calibrate(a):
    from astra.calibrate import calibrate_logs
    cal, info = calibrate_logs([Path(p) for p in a.logs])
    Path(a.out).write_text(json.dumps(cal, indent=1))
    print(json.dumps(info, indent=1))


def _cmd_shield(a):
    from astra import onboard
    if a.action_name == "calibrate":
        cal, info = onboard.calibrate_from_logs(a.logs)
        Path(a.out).write_text(json.dumps(cal, indent=1))
        print(json.dumps(info, indent=1))
        return
    cal = None if a.log_only else json.loads(Path(a.cal).read_text())
    script = onboard.lua_monitor(cal, action={"alert": 0, "land": 1, "nogps-land": 2}[a.on_alarm])
    Path(a.out).write_text(script, encoding="ascii", newline="\n")
    print(f"wrote {a.out} ({'log-only' if cal is None else 'armed, on alarm: ' + a.on_alarm}). "
          f"Copy to the autopilot's APM/scripts/ and set SCR_ENABLE=1.")


def _cmd_advise(a):
    from astra.advise import advise, render
    rows = advise(Path(a.params) if a.params else None, Path(a.out), a.nbenign, a.parallel,
                  a.autopilot, a.gps_profile, settings=a.settings.split(",") if a.settings else None)
    print(render(rows, a.nbenign))


def _cmd_invert(a):
    import yaml
    from astra.detect import monitor
    from astra.forensics import _bundled_calibration, _load
    from astra.inversion import invert
    cal_all = json.loads(Path(a.cal).read_text()) if a.cal else _bundled_calibration()
    fl = _load(Path(a.log))
    cfg = "gps+imu+flow" if (fl.has("OF") and fl.has("RFND") and "gps+imu+flow" in cal_all) else "gps+imu"
    inv = invert(fl, monitor.Calibration(**cal_all[cfg]))
    if inv is None:
        sys.exit("no drag-off spoof detected in this log; nothing to invert")
    import numpy as np
    pos = fl["POS"]
    climb = np.nonzero(pos["RelHomeAlt"] > 0.5)[0]
    t_lift = float(pos["t"][climb[0]]) if len(climb) else None
    # take-off time stands in for arming (logs here carry no explicit arming event): an estimate
    attack = inv.scenario_attack(after_arm_s=max(0.0, inv.onset_s - t_lift) if t_lift is not None else None)
    out = {"estimated_attack": attack, "evidence": {"channel": inv.channel, "onset_s_in_log": round(inv.onset_s, 1),
           "alarm_s_in_log": round(inv.alarm_s, 1), "blocks_used": inv.n_blocks}}
    if a.mission:
        sc = yaml.safe_load(Path(a.mission).read_text())
        sc["attacks"] = [attack]
        sc["id"] = (sc.get("id", "incident") + "-repro")[:60]
        out["scenario"] = sc
    class _NoAlias(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True
    text = yaml.dump(out, Dumper=_NoAlias, sort_keys=False)
    if a.out:
        Path(a.out).write_text(text)
    print(text)
    print("# start.after_arm_s is estimated from take-off time (no arming event in the log): check it.",
          file=sys.stderr)


def _cmd_flowshield_cal(a):
    from astra.companion import calibrate_flow_from_collections
    base = json.loads(Path(a.base).read_text())
    base = base.get("gps+imu+flow", base)
    cal = calibrate_flow_from_collections(a.collections, base)
    Path(a.out).write_text(json.dumps(cal, indent=1))
    print(json.dumps(cal["flow_shield"]))


def _cmd_html(a):
    from astra.html_report import render
    print(render(Path(a.run_dir)))


def main(argv=None):
    p = argparse.ArgumentParser(prog="astra", description="ASTRA Proving Ground")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("packs").set_defaults(fn=_cmd_packs)
    r = sub.add_parser("run")
    r.add_argument("pack")
    r.add_argument("--out", required=True)
    r.add_argument("--params", help="vendor ArduPilot .parm file (default: ArduPilot defaults)")
    r.add_argument("--seeds", type=int, default=3)
    r.add_argument("--parallel", type=int, default=None)
    r.add_argument("--speedup", type=int, default=10)
    r.add_argument("--only", default="", help="substring filter on scenario id")
    r.add_argument("--anchor", action="store_true", help="OpenTimestamps-anchor the report (sends its hash only)")
    r.add_argument("--autopilot", default="ardupilot", choices=["ardupilot", "px4"],
                   help="px4 needs the astra/px4-sitl image (sim/px4)")
    r.set_defaults(fn=_cmd_run)
    v = sub.add_parser("verify")
    v.add_argument("report")
    v.add_argument("--trust", action="append", help="trusted signer fingerprint (repeatable)")
    v.add_argument("--trust-file")
    v.set_defaults(fn=_cmd_verify)
    sub.add_parser("key").set_defaults(fn=_cmd_key)
    lg = sub.add_parser("ledger")
    lg.add_argument("action", choices=["verify"])
    lg.set_defaults(fn=_cmd_ledger)
    d = sub.add_parser("diagnose")
    d.add_argument("log")
    d.add_argument("--cal", help="airframe calibration from `astra calibrate` (default: bundled generic)")
    d.add_argument("--takeoff", help="real take-off point LAT,LON[,RADIUS_M] (power-on spoofing check; "
                                     "radius = how well you know the pad, default 15 m)")
    d.add_argument("--html", metavar="OUT.html", help="write a readable report page instead of printing JSON")
    d.set_defaults(fn=_cmd_diagnose)
    c = sub.add_parser("calibrate", help="per-airframe A2 calibration from benign logs")
    c.add_argument("logs", nargs="+")
    c.add_argument("--out", required=True)
    c.set_defaults(fn=_cmd_calibrate)
    ad = sub.add_parser("advise", help="measured trade-off of EKF parameter changes on your params")
    ad.add_argument("--params", help="vendor .parm (default: ArduPilot defaults)")
    ad.add_argument("--out", required=True)
    ad.add_argument("--nbenign", type=int, default=20)
    ad.add_argument("--parallel", type=int, default=4)
    ad.add_argument("--autopilot", choices=["ardupilot", "px4"], default="ardupilot")
    ad.add_argument("--gps-profile", choices=["typical", "harsh"], default=None,
                    help="GNSS noise for the benign flights (harsh = noisier real receivers)")
    ad.add_argument("--settings", help="comma-separated shortlist of candidate settings to fly (default: all)")
    ad.set_defaults(fn=_cmd_advise)
    iv = sub.add_parser("invert", help="estimate the drag-off attack in a log and emit a reproducible scenario")
    iv.add_argument("log")
    iv.add_argument("--cal", help="calibration (default: bundled)")
    iv.add_argument("--mission", help="your scenario YAML; the estimated attack is inserted into it")
    iv.add_argument("--out")
    iv.set_defaults(fn=_cmd_invert)
    fs = sub.add_parser("flowshield-calibrate", help="fit Flow-Shield from live residuals collected with "
                                                     "`python -m astra.companion --mode flow --collect ...`")
    fs.add_argument("collections", nargs="+")
    fs.add_argument("--base", required=True, help="A2 calibration with a gps+imu+flow entry (`astra calibrate`)")
    fs.add_argument("--out", required=True)
    fs.set_defaults(fn=_cmd_flowshield_cal)
    hp = sub.add_parser("html", help="self-contained HTML view of a run directory")
    hp.add_argument("run_dir")
    hp.set_defaults(fn=_cmd_html)
    sh = sub.add_parser("shield", help="ASTRA Shield onboard monitor (ArduPilot Lua)")
    shs = sh.add_subparsers(dest="action_name", required=True)
    sc_ = shs.add_parser("calibrate", help="fit constants from benign logs flown with the log-only script")
    sc_.add_argument("logs", nargs="+")
    sc_.add_argument("--out", required=True)
    se = shs.add_parser("export", help="write the Lua script")
    se.add_argument("--out", required=True)
    g = se.add_mutually_exclusive_group(required=True)
    g.add_argument("--log-only", action="store_true", help="calibration-collection mode (no alarms)")
    g.add_argument("--cal", help="constants from `astra shield calibrate`")
    se.add_argument("--on-alarm", choices=["alert", "land", "nogps-land"], default="alert",
                    help="nogps-land needs EK3_SRC2_POSXY=0, EK3_SRC2_VELXY=0 (or 5 with flow), EK3_SRC2_YAW=1")
    sh.set_defaults(fn=_cmd_shield)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
