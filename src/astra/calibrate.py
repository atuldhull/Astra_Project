"""Per-airframe A2 calibration from the vendor's own benign flight logs.

    astra calibrate LOG_OR_DIR [LOG_OR_DIR ...] --out my-airframe.json

Accepts ArduPilot .BIN logs or ASTRA flight.npz extracts. Uses only benign flights; never feed it a
log you suspect was attacked. Writes a calibration for each sensor configuration the logs support.
Guidance: ≥ 30 min of airborne time over representative missions, speeds and winds. Less than
that and the threshold (max benign CUSUM peak × margin) is unreliable, so the tool warns.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from astra import logs
from astra.detect import features, monitor

MIN_HOURS = 0.5


def _collect(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        if not p.is_dir():
            out.append(p)
            continue
        for d in sorted({f.parent for f in p.rglob("*")} | {p}):
            npz = d / "flight.npz"
            if npz.exists():
                out.append(npz)  # compact extract wins over the raw log in the same run dir
                continue
            out += sorted(f for f in d.glob("*") if f.suffix.lower() == ".bin"
                          and f.name.lower() != "eeprom.bin" and (d.name == "logs" or f.name[:1].isdigit()))
    return list(dict.fromkeys(out))


def calibrate_logs(paths: list[Path], margin: float = 1.25) -> tuple[dict, dict]:
    chs, skipped = [], []
    for p in _collect(paths):
        try:
            fl = logs.load_npz(p) if p.suffix == ".npz" else logs.load(p)
            if fl.attack_windows():
                skipped.append((str(p), "contains an ASTRA attack label; not benign"))
                continue
            chs.append(features.compute(fl))
        except (ValueError, KeyError, OSError) as exc:
            skipped.append((str(p), str(exc)))
    if not chs:
        raise ValueError("no usable benign logs")
    hours = sum(float(c.airborne.sum()) * features.DT for c in chs) / 3600
    out: dict = {}
    base = monitor.calibrate(chs, ("c1", "c3"), margin)
    out["gps+imu"] = json.loads(base.to_json())
    flow = [c for c in chs if c.c2 is not None and c.c2_valid.any()]
    if flow:
        M = features.fit_flow_model(flow)
        for c in flow:
            features.apply_flow(c, M)
        B = features.fit_flow_nuisance(flow)
        for c in flow:
            features.apply_flow(c, M, B)
        cal = monitor.calibrate(chs, ("c1", "c2", "c3"), margin)
        cal.flow_model, cal.flow_nuisance = M.tolist(), B.tolist()
        out["gps+imu+flow"] = json.loads(cal.to_json())
    info = {"flights": len(chs), "airborne_hours": round(hours, 3), "skipped": skipped,
            "configs": list(out), "warning": None}
    if hours < MIN_HOURS:
        info["warning"] = (f"only {hours:.2f} h of airborne data (< {MIN_HOURS} h): thresholds will be "
                           f"unreliable; fly more benign missions before trusting alarms")
    return out, info
