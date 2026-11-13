"""Build src/astra/data/evidence.json: the test record shown in `astra ui` -> "How well it works".

Everything comes from committed files (selection lists, per-flight result rows, scored reports); nothing is
re-scored here. Gates v6/v7 only kept the flagged flight ids in their reports, so their other usable flights are
recorded as "no anomaly", exactly as the report counts them.

usage: python benchmarks/build_evidence.py
"""
import json
import re
from pathlib import Path

from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/atuldhull/Astra_Project/blob/v4/"
CLS = [("no GNSS", "none"), ("spoofing-like", "spoof"), ("jamming-like", "jam"), ("inconclusive", "inconclusive"),
       ("RF-attack-like", "rf"), ("mixed", "mixed"), ("not analysed", "notflown")]


def cls(verdict: str) -> str:
    return next((c for p, c in CLS if verdict.startswith(p)), "other")


def upper95(k: int, n: int) -> float:
    return float(beta.ppf(0.975, k + 1, n - k)) if n else 1.0  # Clopper-Pearson one-sided-ish upper bound


def from_md(name, sel, md, code, date):
    text = (ROOT / md).read_text(encoding="utf-8")
    ids = [e["log_id"] for e in json.loads((ROOT / sel).read_text())]
    flagged, unusable = {}, set()
    for c, label in (("spoof", "spoofing-like"), ("inconclusive", "inconclusive"), ("jam", "jamming-like"),
                     ("rf", "RF-attack-like")):
        m = re.search(rf"^- {re.escape(label)}: (.+)$", text, re.M)
        if m:
            for p in re.findall(r"[0-9a-f]{8}", m.group(1)):
                flagged[p] = c
    um = text.split("Unusable logs:")[1].split("\n\n")[0] if "Unusable logs:" in text else ""
    unusable = set(re.findall(r"^- ([0-9a-f]{8}):", um, re.M))
    flights = []
    for i in ids:
        if i[:8] in unusable:
            continue
        flights.append({"id": i, "c": flagged.get(i[:8], "none")})
    return {"name": name, "date": date, "code": code, "selection": REPO + sel, "report": REPO + md, "flights": flights}


def from_rows(name, sel, rows, md, code, date):
    flights = []
    for line in (ROOT / rows).read_text().splitlines():
        r = json.loads(line)
        if "verdict" not in r:
            continue
        flights.append({"id": r["log_id"], "c": cls(r["verdict"]), "v": r["verdict"][:160], "loc": r.get("loc1deg")})
    return {"name": name, "date": date, "code": code, "selection": REPO + sel, "report": REPO + md,
            "rows": REPO + rows, "flights": flights}


def counts(flights):
    c = {}
    for f in flights:
        c[f["c"]] = c.get(f["c"], 0) + 1
    return c


ATTACKS = [
    {"source": "IEEE DataPort UAV Attack Dataset", "kind": "jamming", "how": "live HackRF jamming, PX4 quad hovering ~1 m indoors",
     "blind": "no anomaly", "blind_ok": False, "after": "RF-attack-like", "after_ok": True,
     "report": REPO + "benchmarks/ieee-real-attacks-v1.md", "data": "https://ieee-dataport.org/open-access/uav-attack-dataset"},
    {"source": "IEEE DataPort UAV Attack Dataset", "kind": "spoofing", "how": "live HackRF spoofing (GPS-SDR-SIM), same drone",
     "blind": "no anomaly", "blind_ok": False, "after": "RF-attack-like", "after_ok": True,
     "report": REPO + "benchmarks/ieee-real-attacks-v1.md", "data": "https://ieee-dataport.org/open-access/uav-attack-dataset"},
    {"source": "Public PX4 log, pilot-labelled \"YAF 3_SPOOF\"", "kind": "spoofing test", "how": "all satellites lost for ~150 s in flight",
     "blind": "jamming-like", "blind_ok": True, "after": "jamming-like", "after_ok": True,
     "report": REPO + "benchmarks/wild-attacks-v1.md",
     "data": "https://review.px4.io/plot_app?log=5d07d813-8bff-4a92-9ee6-f9e8469b347b"},
    {"source": "Jammertest 2023, Norway (FGI recording)", "kind": "jamming", "how": "high-power noise jamming, test 4.1.5",
     "blind": "RF-attack-like", "blind_ok": True, "after": "RF-attack-like", "after_ok": True,
     "report": REPO + "benchmarks/jammertest-v1.md", "data": "https://etsin.fairdata.fi/dataset/2eee8cfd-db00-4e46-bd62-d7632c09c700"},
    {"source": "Jammertest 2023, Norway (FGI recording)", "kind": "spoofing (incoherent)", "how": "receiver captured ~249 km away for 9 min, test 16.1.1",
     "blind": "RF-attack-like (attack found, not named spoofing)", "blind_ok": True,
     "after": "RF-attack-like + 249 km jump flagged as spoofing evidence", "after_ok": True,
     "report": REPO + "benchmarks/jammertest-v1.md", "data": "https://etsin.fairdata.fi/dataset/2eee8cfd-db00-4e46-bd62-d7632c09c700"},
    {"source": "Jammertest 2023, Norway (FGI recording)", "kind": "spoofing (coherent)", "how": "fake position dragged round a 1 km loop at 25 m/s, test 17.1.6",
     "blind": "RF-attack-like (attack found, not named spoofing)", "blind_ok": True,
     "after": "RF-attack-like; the drag itself still not identified", "after_ok": True,
     "report": REPO + "benchmarks/jammertest-v1.md", "data": "https://etsin.fairdata.fi/dataset/2eee8cfd-db00-4e46-bd62-d7632c09c700"},
]


def main():
    gates = [
        from_md("Gate v6", "runs/px4_real6_sel.json", "benchmarks/real-gate-v6.md", "b653c34", "2026-11-11"),
        from_md("Gate v7", "runs/px4_real7_sel.json", "benchmarks/real-gate-v7.md", "cd201fd", "2026-11-12"),
        from_rows("Gate v8", "runs/px4_real8_sel.json", "runs/gate-v8.jsonl", "benchmarks/real-gate-v8.md", "673b37d", "2026-11-12"),
        from_rows("Gate v9", "runs/px4_real9_sel.json", "runs/gate-v9.jsonl", "benchmarks/real-gate-v9.md", "1298454", "2026-11-13"),
    ]
    for g in gates:
        g["counts"] = counts(g["flights"])
        g["n"] = len(g["flights"])
    expected = {"Gate v6": 345, "Gate v7": 349, "Gate v8": 347, "Gate v9": 346}
    for g in gates:
        assert g["n"] == expected[g["name"]], (g["name"], g["n"])
    scan = from_rows("In-the-wild scan", "runs/px4_wildscan_sel.json", "runs/wildscan-v1.jsonl",
                     "benchmarks/wildscan-v1.md", "f8099fa", "2026-11-12")
    scan["counts"] = counts(scan["flights"])
    scan["n"] = len(scan["flights"])
    n = sum(g["n"] for g in gates)
    sp = sum(g["counts"].get("spoof", 0) for g in gates)
    rf_n = sum(g["n"] for g in gates[1:])  # RF-attack-like exists from v7 on
    rf = sum(g["counts"].get("rf", 0) for g in gates[1:])
    inc = sum(g["counts"].get("inconclusive", 0) for g in gates)
    blind = sum(a["blind_ok"] for a in ATTACKS)
    out = {
        "repo": REPO, "built_from": "benchmarks/build_evidence.py",
        "headline": {
            "false_spoof": {"k": sp, "n": n, "upper95": round(upper95(sp, n), 4)},
            "false_rf": {"k": rf, "n": rf_n, "upper95": round(upper95(rf, rf_n), 4)},
            "inconclusive": {"k": inc, "n": n},
            "attacks_blind": {"k": blind, "n": len(ATTACKS)},
            "attacks_after": {"k": sum(a["after_ok"] for a in ATTACKS), "n": len(ATTACKS)},
            "spoof_named_blind": {"k": 0, "n": 4},
        },
        "attacks": ATTACKS, "gates": gates, "scan": scan,
    }
    p = ROOT / "src/astra/data/evidence.json"
    p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(p, f"{p.stat().st_size / 1e3:.0f} kB", out["headline"])


if __name__ == "__main__":
    main()
