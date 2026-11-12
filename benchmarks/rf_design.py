"""Design data for two real-attack fixes (ieee-real-attacks-v1.md), measured on real BENIGN flights:

  * receiver noise rise: max over the flight of the sustained (T s) ratio noise / trailing baseline
    (baseline = median noise 30-120 s earlier), airborne only
  * 1-Hz step residual: |dp - v_mean*dt| for fixes 0.5-1.5 s apart, airborne only

usage: python benchmarks/rf_design.py OUT.json DIR_OR_GLOB ...
"""
import glob, json, sys, warnings
from pathlib import Path
from multiprocessing import Pool
import numpy as np


def noise_rise(t, x, air, T):
    out = 0.0
    ok = np.isfinite(x) & (x > 0)
    for i in np.nonzero(air & ok)[0]:
        b = (t >= t[i] - 120) & (t <= t[i] - 30) & ok
        if b.sum() < 20:
            continue
        base = np.median(x[b])
        w = (t >= t[i]) & (t <= t[i] + T) & ok
        if w.sum() < max(2, T * 0.5) or t[w][-1] - t[i] < T * 0.8 or not air[w].all():
            continue
        out = max(out, float(np.min(x[w]) / base))
    return out


def one(f):
    warnings.filterwarnings("ignore")
    from astra.forensics import _load
    from astra.geo import latlon_to_ne
    try:
        fl = _load(Path(f))
    except Exception as e:  # noqa: BLE001
        return {"f": f, "err": str(e)[:60]}
    g = fl["GPS"]; t = g["t"]; air = fl.airborne(t)
    r = {"f": f, "gps_dt": float(np.median(np.diff(t))), "air_s": float(air.sum() * np.median(np.diff(t))),
         "has_land": fl.has("LAND")}
    if "Noise" in g:
        x = g["Noise"].astype(float)
        r["noise_med"] = float(np.median(x[air])) if air.any() else None
        for T in (3, 5, 10):
            r[f"rise{T}"] = noise_rise(t, x, air, T)
    ok = g["Status"] >= 3
    tt, la, lo = t[ok], g["Lat"][ok], g["Lng"][ok]
    if len(tt) > 3:
        n, e = latlon_to_ne(la[0], lo[0], la, lo)
        crs = np.radians(g["GCrs"][ok]); vn, ve = g["Spd"][ok] * np.cos(crs), g["Spd"][ok] * np.sin(crs)
        dt = np.diff(tt)
        res = np.hypot(np.diff(n) - 0.5 * (vn[1:] + vn[:-1]) * dt, np.diff(e) - 0.5 * (ve[1:] + ve[:-1]) * dt)
        m = (dt >= 0.5) & (dt <= 1.5) & fl.airborne(tt[1:])
        r["step1hz_n"] = int(m.sum()); r["step1hz_max"] = float(res[m].max()) if m.any() else None
        r["step1hz_p999"] = float(np.percentile(res[m], 99.9)) if m.sum() > 50 else None
    return r


if __name__ == "__main__":
    files = [f for a in sys.argv[2:] for f in (sorted(glob.glob(a + "/*.ulg")) if not any(c in a for c in "*?") else sorted(glob.glob(a, recursive=True)))]
    with Pool(4) as p:
        rows = p.map(one, files, chunksize=2)
    json.dump(rows, open(sys.argv[1], "w"), indent=0)
    print(len(rows), "flights")
