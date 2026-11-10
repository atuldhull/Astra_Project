import re

from astra.onboard import lua_monitor

CAL = {"sigma_inv": [[4.0, 0.5], [0.5, 3.0]], "k": 2.5, "h": 120.0}


def test_log_only_mode_has_no_alarm_logic_enabled():
    s = lua_monitor(None)
    assert "local ARMED = false" in s


def test_armed_mode_embeds_calibration_constants():
    s = lua_monitor(CAL)
    assert "local ARMED = true" in s
    assert "local S00, S01, S11 = 4.0, 0.5, 3.0" in s
    assert "local K, H = 2.5, 120.0" in s


def test_alert_only_by_default_and_never_writes_params():
    s = lua_monitor(CAL)
    assert "local ACTION = 0" in s
    assert "param:set" not in s and "Parameter(" not in s
    # the only flight-affecting call is gated behind ACTION >= 1
    calls = re.findall(r"vehicle:set_mode\(", s)
    assert len(calls) == 1 and "if ACTION >= 1 then vehicle:set_mode(9)" in s


def test_deterministic():
    assert lua_monitor(CAL) == lua_monitor(CAL)
