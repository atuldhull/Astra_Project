"""GNSS-SDR output on a Jammertest recording -> ASTRA FlightLog (.npz), "bench mode".

Bench mode (stated limits): the recorder was static (checked: pre-attack fixes stay within a few metres), so the
IMU is a truthful stationary IMU (gravity only), the vehicle is marked airborne from 5 s after the receiver's first fix (land
detector) and POS follows the receiver. GPS rows exist every 200 ms over the whole recording; where the
receiver produced no fix the row has fix 1 / 0 satellites, as PX4 logs it. The receiver "noise" field is the
recording's full-band power (an AGC-like level, chosen before scoring); there is no receiver self-report.

usage: python benchmarks/jammertest_to_log.py NAME [SUB]   (reads runs/jammertest/NAME_spectrum_stats.npz and SUB_NAME/;
       SUB = out (harness v1, raw receiver positions) or kf (v2, receiver navigation filter on))
"""
import re
import sys
from pathlib import Path

import numpy as np

from astra.logs import FlightLog, save_npz

REC = np.dtype([("tow_ms", "<u4"), ("week", "<u4"), ("rx_time", "<f8"), ("clk", "<f8"), ("rr", "<f8", 6),
                ("qr", "<f8", 6), ("lat", "<f8"), ("lon", "<f8"), ("h", "<f8"), ("ns", "u1"), ("stat", "u1"),
                ("type", "u1"), ("ratio", "<f4"), ("thres", "<f4"), ("dop", "<f8", 4)])
assert REC.itemsize == 187


def file_time_offset(console: str) -> float:
    """Recording time (s) minus GPS time of week (s), from the receiver's console (+/- 1 s)."""
    last_rx = 0
    for line in re.sub(r"\x1b\[[0-9;]*m", "", console).splitlines():
        m = re.match(r"Current receiver time: (\d+) s", line)
        if m:
            last_rx = int(m.group(1))
        m = re.search(r"Position at \d{4}-\w{3}-\d+ (\d+):(\d+):([\d.]+) UTC", line)
        if m:
            sod_utc = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            return last_rx, sod_utc
    raise ValueError("no fix in console log")


def main(name, sub="out"):
    base = Path("runs/jammertest")
    out = base / f"{sub}_{name}"
    p = np.fromfile(out / "pvt.dat", REC)
    p = p[p["stat"] > 0]
    # GPS time of week -> recording time. Console gives receiver time (s since file start) at the first fix (UTC).
    rx_at_fix, sod_utc = file_time_offset((out / "console.log").read_text(errors="replace"))
    sod_gps = np.mod(p["rx_time"], 86400.0)  # GPS seconds of day; GPS - UTC = 18 s
    t_fix = sod_gps - (sod_utc + 18.0) + rx_at_fix
    st = np.load(base / f"{name}_spectrum_stats.npz")
    T = float(st["t"][-1])
    t = np.arange(0.0, T, 0.2)
    k = np.clip(np.searchsorted(t_fix, t), 1, len(t_fix) - 1)
    k = np.where(np.abs(t_fix[k - 1] - t) < np.abs(t_fix[k] - t), k - 1, k)
    has = np.abs(t_fix[k] - t) <= 0.3
    lat, lon, h = np.radians(p["lat"][k]), np.radians(p["lon"][k]), p["h"][k]
    vx, vy, vz = p["rr"][k, 3], p["rr"][k, 4], p["rr"][k, 5]
    vn = -np.sin(lat) * np.cos(lon) * vx - np.sin(lat) * np.sin(lon) * vy + np.cos(lat) * vz
    ve = -np.sin(lon) * vx + np.cos(lon) * vy
    vd = -(np.cos(lat) * np.cos(lon) * vx + np.cos(lat) * np.sin(lon) * vy + np.sin(lat) * vz)
    # Harness v2: RTKLIB's single-epoch covariance (6-16 m) is not comparable with a u-blox hAcc (1-3 m when
    # healthy, also under a coherent spoofer), and made ASTRA call the whole recording "degraded" (v1, blind).
    hacc = p["dop"][k, 2] * 1.5
    nan = np.full(len(t), np.nan)
    fl = FlightLog(f"jammertest:{name}")
    fl.series["GPS"] = {"t": t, "Status": np.where(has, 3.0, 1.0), "NSats": np.where(has, p["ns"][k], 0).astype(float),
                        "HDop": np.where(has, p["dop"][k, 2], 99.0), "Lat": np.degrees(lat), "Lng": np.degrees(lon),
                        "Alt": h, "Spd": np.where(has, np.hypot(vn, ve), 0.0),
                        "GCrs": np.degrees(np.arctan2(ve, vn)) % 360, "VZ": np.where(has, vd, 0.0),
                        "Noise": np.interp(t, st["t"], st["stats"][:, 0]) * 20.0}
    fl.series["GPA"] = {"t": t, "HAcc": np.where(has, hacc, 1e4), "VAcc": np.where(has, hacc * 1.6, 1e4), "SAcc": nan}
    ok = has.nonzero()[0]
    fl.series["POS"] = {"t": t, "Lat": np.interp(t, t[ok], np.degrees(lat)[ok]), "Lng": np.interp(t, t[ok], np.degrees(lon)[ok]),
                        "Alt": np.interp(t, t[ok], h[ok]), "RelHomeAlt": np.full(len(t), 10.0)}
    ti = np.arange(0.0, T, 0.02)
    z = np.zeros(len(ti))
    fl.series["IMU"] = {"t": ti, "I": z, "AccX": z, "AccY": z, "AccZ": np.full(len(ti), -9.81)}
    fl.series["ATT"] = {"t": ti, "Roll": z, "Pitch": z, "Yaw": z}
    # "take-off" 5 s after the receiver's first fix (a drone does not fly during the cold start)
    fl.series["LAND"] = {"t": np.array([0.0, t_fix[0] + 5.0, T]), "Landed": np.array([1.0, 0.0, 0.0])}
    save_npz(fl, base / f"{name}_{sub}_bench.npz")
    print(f"{name}: {len(t)} rows, fixes {has.mean():.0%}, first fix at {t_fix[0]:.1f} s, "
          f"pre-attack spread {np.ptp(p['lat'][:50]) * 111e3:.1f} m N")


if __name__ == "__main__":
    main(*sys.argv[1:3])
