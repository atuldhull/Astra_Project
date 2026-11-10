"""astra: command-line interface.

  astra packs                              list built-in scenario packs
  astra run PACK --out DIR [options]       fly a pack, write signed report
  astra verify REPORT --trust FP           verify a signed report (offline)
  astra key                                show this installation's signing fingerprint
  astra ledger verify                      re-walk the local hash-chained ledger
  astra diagnose LOG.BIN|flight.npz        forensics on a flight log (A2 monitor)
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

    res = run_batch(jobs, out, parallel=a.parallel, speedup=a.speedup, vendor_param_file=vend, on_result=tick)
    results = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
    body = build_body(a.pack, scs, results, seeds=a.seeds, speedup=a.speedup, vendor_param_file=vend)
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
    print(json.dumps(diagnose(Path(a.log)), indent=1, default=str))


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
    d.set_defaults(fn=_cmd_diagnose)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
