"""Scan recent public PX4 logs for real-world GNSS interference (unlabelled; 'likely', never 'confirmed').

Each log is downloaded, run through frozen `astra diagnose`, summarised and deleted immediately (disk stays small).
Flags: receiver self-report level 3, RF-attack-like events, airborne fix loss >= 10 s, spoofing-like verdicts.
Coarse location only (1 degree) is kept.
usage: python benchmarks/wild_scan.py SEL.json OUT.jsonl
"""
import json, os, subprocess, sys, tempfile, warnings
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from pathlib import Path


def analyse(path):
    warnings.filterwarnings("ignore")
    import numpy as np
    from astra.forensics import diagnose, _load
    try:
        r = diagnose(Path(path)); fl = _load(Path(path)); g = fl["GPS"]; ok = g["Status"] >= 3
        loc = [round(float(np.median(g["Lat"][ok]))), round(float(np.median(g["Lng"][ok])))] if ok.any() else None
        rc = r["receiver"]
        return {"verdict": r["verdict"][:160], "loc1deg": loc, "rf": rc.get("rf_interference"),
                "self": rc.get("self_report"), "fix_lost": rc["fix_lost_intervals_s"],
                "spoof_ev": r["evidence"]["spoofing_events"][:5]}
    except Exception as e:  # noqa: BLE001
        return {"err": f"{type(e).__name__}: {str(e)[:80]}"}


def fetch(entry, tmp):
    f = Path(tmp) / f"{entry['log_id']}.ulg"
    rc = subprocess.run(["curl", "-sfL", "--retry", "4", "-m", "300", "-o", str(f), entry["url"]]).returncode
    return f if rc == 0 and f.exists() and f.stat().st_size > 0 else None


if __name__ == "__main__":
    sel, out = json.load(open(sys.argv[1])), Path(sys.argv[2])
    done = {json.loads(l)["log_id"] for l in out.read_text().splitlines()} if out.exists() else set()
    todo = [e for e in sel if e["log_id"] not in done]
    tmp = tempfile.mkdtemp(prefix="wildscan_", dir="runs")
    with ThreadPoolExecutor(4) as dl, Pool(3) as cpu, out.open("a") as fo:
        for i in range(0, len(todo), 12):
            batch = todo[i:i + 12]
            files = list(dl.map(lambda e: fetch(e, tmp), batch))
            res = cpu.map(analyse, [str(f) for f in files if f])
            it = iter(res); res = [next(it) if f else None for f in files]
            for e, f, r in zip(batch, files, res):
                row = {"log_id": e["log_id"], "ver": e.get("ver"), "hw": e.get("hw"), **(r if f else {"err": "download failed"})}
                fo.write(json.dumps(row) + "\n"); fo.flush()
                if f:
                    os.remove(f)
            print(f"{i + len(batch)}/{len(todo)}", flush=True)
