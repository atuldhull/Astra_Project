"""ArduPilot dataflash (.BIN) → column arrays.

Only the message types ASTRA needs are decoded. Each type becomes a dict of
numpy arrays with a common `t` column (seconds since boot).

Works for real flight logs (no SIM/ASTK) as well as SITL logs (SIM = simulator
truth, ASTK = ASTRA ground-truth attack label).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from pymavlink import DFReader

WANTED = {
    "GPS": ("Status", "NSats", "HDop", "Lat", "Lng", "Alt", "Spd", "GCrs", "VZ"),
    "GPA": ("HAcc", "VAcc", "SAcc"),
    "POS": ("Lat", "Lng", "Alt", "RelHomeAlt"),
    "SIM": ("Lat", "Lng", "Alt"),
    "XKF1": ("C", "VN", "VE", "VD", "PN", "PE", "PD"),
    "XKF3": ("C", "IVN", "IVE", "IVD", "IPN", "IPE", "IPD"),
    "XKF4": ("C", "SV", "SP", "SH", "SM", "FS", "TS", "SS", "GPS"),
    "XKF2": ("C", "AX", "AY", "AZ", "VWN", "VWE"),
    "OF": ("Qual", "flowX", "flowY", "bodyX", "bodyY"),
    "RFND": ("Instance", "Dist", "Stat"),
    "IMU": ("I", "AccX", "AccY", "AccZ"),
    "ATT": ("Roll", "Pitch", "Yaw"),
    "BARO": ("I", "Alt"),
    "CTUN": ("ThO", "Alt", "DAlt"),
    "RCOU": ("C1", "C2", "C3", "C4"),
    "ASTK": ("Act", "Code", "OfsN", "OfsE", "VbN", "VbE", "En", "Jam"),
    "ASTM": ("rN", "rE", "q", "S", "Al"),  # ASTRA Shield onboard monitor blocks
}
# Messages with an instance/core column: keep the primary only (C/I == 0).
PRIMARY_ONLY = {"XKF1": "C", "XKF2": "C", "XKF3": "C", "XKF4": "C", "IMU": "I", "BARO": "I", "RFND": "Instance"}


@dataclass
class FlightLog:
    path: str
    series: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)
    messages: list[tuple[float, str]] = field(default_factory=list)
    modes: list[tuple[float, int]] = field(default_factory=list)
    params: dict[str, float] = field(default_factory=dict)

    def has(self, typ: str) -> bool:
        return typ in self.series and len(self.series[typ]["t"]) > 0

    def __getitem__(self, typ: str) -> dict[str, np.ndarray]:
        return self.series[typ]

    @property
    def is_sitl(self) -> bool:
        return self.has("SIM")

    def attack_windows(self) -> list[tuple[float, float, int]]:
        """Ground-truth (start, end, code) intervals from ASTK. Empty for real logs."""
        if not self.has("ASTK"):
            return []
        a = self["ASTK"]
        act = a["Act"] > 0
        out, start, code = [], None, 0
        for t, on, c in zip(a["t"], act, a["Code"]):
            if on and start is None:
                start, code = t, int(c)
            elif not on and start is not None:
                out.append((float(start), float(t), code))
                start = None
        if start is not None:
            out.append((float(start), float(a["t"][-1]), code))
        return out


def load(path: str | Path) -> FlightLog:
    r = DFReader.DFReader_binary(str(path), zero_time_base=False)
    types = set(WANTED) | {"MSG", "MODE", "PARM"}
    cols: dict[str, dict[str, list]] = {k: {"t": [], **{f: [] for f in v}} for k, v in WANTED.items()}
    fl = FlightLog(str(path))
    while True:
        m = r.recv_match(type=types)
        if m is None:
            break
        typ = m.get_type()
        if typ == "MSG":
            fl.messages.append((m.TimeUS / 1e6, m.Message))
            continue
        if typ == "MODE":
            fl.modes.append((m.TimeUS / 1e6, int(m.ModeNum)))
            continue
        if typ == "PARM":
            fl.params[m.Name] = float(m.Value)
            continue
        inst = PRIMARY_ONLY.get(typ)
        if inst is not None and getattr(m, inst, 0) != 0:
            continue
        c = cols[typ]
        c["t"].append(m.TimeUS / 1e6)
        for f in WANTED[typ]:
            c[f].append(getattr(m, f, np.nan))
    r.close()  # release the mmap/file handle (Windows can't delete an open file)
    for typ, c in cols.items():
        fl.series[typ] = {k: np.asarray(v, dtype=float) for k, v in c.items()}
    return fl


def save_npz(fl: FlightLog, path: str | Path) -> None:
    """Compact, analysis-ready extract (a few hundred kB instead of tens of MB)."""
    arrays = {f"{typ}.{col}": arr for typ, cols in fl.series.items() for col, arr in cols.items()}
    arrays["_messages_t"] = np.asarray([t for t, _ in fl.messages], dtype=float)
    arrays["_messages_text"] = np.asarray([m for _, m in fl.messages], dtype=str)
    arrays["_modes"] = np.asarray(fl.modes, dtype=float).reshape(-1, 2)
    np.savez_compressed(path, **arrays)


def load_npz(path: str | Path) -> FlightLog:
    z = np.load(path, allow_pickle=False)
    fl = FlightLog(str(path))
    for key in z.files:
        if key.startswith("_"):
            continue
        typ, col = key.split(".", 1)
        fl.series.setdefault(typ, {})[col] = z[key]
    fl.messages = list(zip(z["_messages_t"].tolist(), z["_messages_text"].tolist()))
    fl.modes = [(float(a), int(b)) for a, b in z["_modes"].tolist()]
    return fl
