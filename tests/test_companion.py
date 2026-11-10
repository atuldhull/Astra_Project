import numpy as np

from astra.companion import ShieldState
from astra.logs import FlightLog
from astra.onboard import shield_blocks


def _track(drag_from=None):
    t = np.arange(0, 120, 0.2)
    north = 8.0 * t
    rng = np.random.default_rng(1)
    north = north + rng.normal(0, 0.05, len(t))
    if drag_from is not None:
        north = north + np.clip(t - drag_from, 0, None) * 1.0  # naive drag: position only
    lat = 27.0 + north / 111319.49079327357
    return t, lat


def test_online_companion_matches_offline_mirror():
    t, lat = _track(drag_from=60)
    fl = FlightLog("synthetic")
    fl.series["GPS"] = {"t": t, "Status": np.full(len(t), 3.0), "Lat": lat, "Lng": np.full(len(t), 71.0),
                        "Spd": np.full(len(t), 8.0), "GCrs": np.zeros(len(t))}
    fl.series["POS"] = {"t": t, "RelHomeAlt": np.full(len(t), 30.0)}
    T, B = shield_blocks(fl)
    st = ShieldState(np.eye(2) * 100.0, k=2.5, h=1e9)
    for ti, la in zip(t, lat):
        st.feed(float(ti), int(round(la * 1e7)), 710000000, 8.0, 0.0, True)
    online = np.array([[b[1], b[2]] for b in st.blocks])
    assert len(online) == len(B)
    assert np.allclose(online, B, atol=0.02)  # integer 1e-7 deg quantisation only
    assert B[-1][0] > 0.8  # the 1 m/s naive drag shows up in the north residual


def test_companion_alarms_on_drag_not_on_clean_track():
    S = np.eye(2) * (1 / 0.05 ** 2)
    for drag, expect in ((None, False), (60, True)):
        t, lat = _track(drag)
        st = ShieldState(S, k=2.5, h=200.0)
        fired = any(st.feed(float(ti), int(round(la * 1e7)), 710000000, 8.0, 0.0, True) for ti, la in zip(t, lat))
        assert fired is expect
