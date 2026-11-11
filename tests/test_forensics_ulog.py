import numpy as np

from astra.ulog import _quat_to_euler_deg


def test_quaternion_identity_and_yaw():
    r, p, y = _quat_to_euler_deg(np.array([1.0]), np.array([0.0]), np.array([0.0]), np.array([0.0]))
    assert np.allclose([r[0], p[0], y[0]], [0, 0, 0])
    h = np.radians(90) / 2
    r, p, y = _quat_to_euler_deg(np.array([np.cos(h)]), np.array([0.0]), np.array([0.0]), np.array([np.sin(h)]))
    assert np.isclose(y[0], 90.0) and np.isclose(r[0], 0) and np.isclose(p[0], 0)


def test_quaternion_pitch():
    h = np.radians(20) / 2
    r, p, y = _quat_to_euler_deg(np.array([np.cos(h)]), np.array([0.0]), np.array([np.sin(h)]), np.array([0.0]))
    assert np.isclose(p[0], 20.0)


def test_step_residual_flags_a_jump_not_smooth_motion():
    from astra.forensics import _step_residual
    from astra.logs import FlightLog
    t = np.arange(0, 60, 0.2)
    north = 10.0 * t  # 10 m/s straight north
    north[t >= 30] += 100.0  # a 100 m jump at t = 30 s
    lat = 27.0 + north / 111319.49
    fl = FlightLog("synthetic")
    fl.series["GPS"] = {"t": t, "Status": np.full(len(t), 3.0), "Lat": lat, "Lng": np.full(len(t), 71.0),
                        "Spd": np.full(len(t), 10.0), "GCrs": np.zeros(len(t))}
    fl.series["POS"] = {"t": t, "RelHomeAlt": np.full(len(t), 30.0)}
    st, ss = _step_residual(fl)
    assert ss.max() > 90 and abs(st[np.argmax(ss)] - 30.0) < 0.3
    assert np.sort(ss)[-2] < 0.01  # everything else is explained by the reported velocity


def test_takeoff_check_flags_boot_offset_not_true_pad():
    from astra.forensics import takeoff_check
    from astra.logs import FlightLog
    t = np.arange(0, 60, 0.2)
    fl = FlightLog("synthetic")
    lat0, lon0 = 27.0, 71.0
    fl.series["GPS"] = {"t": t, "Status": np.full(len(t), 3.0), "Lat": np.full(len(t), lat0),
                        "Lng": np.full(len(t), lon0)}
    fl.series["POS"] = {"t": t, "RelHomeAlt": np.where(t > 20, 30.0, 0.0)}
    assert not takeoff_check(fl, lat0, lon0)["mismatch"]
    far = takeoff_check(fl, lat0 + 100 / 111319.49, lon0)  # GPS says 100 m south of the real pad
    assert far["mismatch"] and abs(far["offset_m"] - 100) < 1
