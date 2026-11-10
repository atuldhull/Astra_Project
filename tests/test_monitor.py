"""A2 monitor statistics on synthetic channels (no simulator)."""

import numpy as np

from astra.detect import monitor
from astra.detect.features import DT, Channels


def _ch(seed, n=6000, shift_at=None, shift=(0.0, 0.0), spike_at=None, sigma=0.8):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * DT
    r = rng.normal(0, sigma, (n, 2))
    if shift_at is not None:
        r[t >= shift_at] += shift
    if spike_at is not None:
        r[int(spike_at / DT)] = (40.0, -40.0)  # one bad flow frame
    ok = np.ones(n, bool)
    return Channels(t, ok, c1=r * 0.1, c3=r.copy(), c2=r.copy(), c2_valid=ok)


def _cal(chs):
    return monitor.calibrate(chs, channels=("c2", "c3"))


def test_no_alarm_on_fresh_noise_at_calibrated_threshold():
    cal = _cal([_ch(s) for s in range(20)])
    alarms = sum(monitor.run(_ch(100 + s), cal)[0].alarm for s in range(20))
    assert alarms <= 1


def test_sustained_shift_is_detected_after_onset():
    cal = _cal([_ch(s) for s in range(20)])
    det, _ = monitor.run(_ch(7, shift_at=200.0, shift=(1.0, 0.0)), cal)
    assert det.alarm and det.t_alarm >= 200.0
    assert det.t_alarm - 200.0 < 120.0


def test_single_spike_does_not_alarm_with_block_median():
    cal = _cal([_ch(s) for s in range(20)])
    det, _ = monitor.run(_ch(3, spike_at=300.0), cal)
    assert not det.alarm


def test_block_median_ignores_spike_but_mean_does_not():
    t = np.arange(40) * DT
    r = np.zeros((40, 2)); r[5] = (40.0, 40.0)
    ok = np.ones(40, bool)
    _, med, _ = monitor.blocks(t, r, ok, 4.0, robust=True)
    _, mean, _ = monitor.blocks(t, r, ok, 4.0, robust=False)
    assert np.allclose(med, 0.0) and mean[0, 0] == 1.0


def test_calibration_round_trips_json():
    cal = _cal([_ch(s) for s in range(5)])
    cal2 = monitor.Calibration.from_json(cal.to_json())
    assert cal2.h == cal.h and cal2.k == cal.k
