import numpy as np

from astra import logs
from astra.forensics import diagnose


def test_receiver_spoof_flags_inside_outage_are_reported(tmp_path):
    """wildscan-v1.md gap: level-3 receiver spoof flags during a fix loss must show up in the verdict."""
    fl = logs.load_npz("examples/benign.npz")
    g = fl["GPS"]
    t = g["t"]
    air = fl.airborne(t)
    mid = t[air][len(t[air]) // 2]
    out = (t >= mid) & (t < mid + 20)
    g["Status"] = np.where(out, 1.0, g["Status"])
    g["NSats"] = np.where(out, 0.0, g["NSats"])
    g["JamState"] = np.ones(len(t))
    g["SpoofState"] = np.where(out & (t < mid + 5), 3.0, 1.0)
    p = tmp_path / "x.npz"
    logs.save_npz(fl, p)
    rep = diagnose(str(p))
    assert rep["verdict"].startswith("jamming-like")
    assert "flagged spoofing (level 3)" in rep["verdict"]
