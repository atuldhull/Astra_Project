import pytest

from astra.runner_px4 import attack_params
from astra.scenario import Scenario

BASE = {"id": "p-1", "title": "t", "home": {"lat": 27.0, "lon": 71.0, "alt_m": 200},
        "mission": {"takeoff_alt_m": 30, "waypoints": [{"north_m": 1000, "east_m": 0, "alt_m": 30}]}}


def sc(att):
    return Scenario.model_validate({**BASE, "attacks": [att] if att else []})


def test_no_attack():
    assert attack_params(sc(None)) == ({"ASTRA_ATK_MODEL": 0}, None)


def test_drag_after_arm_maps_exactly():
    p, t0 = attack_params(sc({"model": "spoof_drag", "start": {"after_arm_s": 40, "delay_s": 5}, "duration_s": 100,
                              "rate_ms": 1.5, "bearing_deg": 45, "consistent": False, "ramp_s": 20}))
    assert t0 == 45 and p["ASTRA_ATK_MODEL"] == 4 and p["ASTRA_ATK_RATE"] == 1.5
    assert p["ASTRA_ATK_CONS"] == 0 and p["ASTRA_ATK_RAMP"] == 20 and p["ASTRA_ATK_DUR"] == 100


def test_waypoint_trigger_is_approximated_and_reported():
    p, t0 = attack_params(sc({"model": "jam_denial", "start": {"at_waypoint": 1, "delay_s": 10}, "duration_s": 30}))
    assert p["ASTRA_ATK_MODEL"] == 1 and t0 == pytest.approx(30 / 1.5 + 8 + 10)


def test_meaconing_and_chaotic_map_to_patch_models():
    p, _ = attack_params(sc({"model": "meaconing", "start": {"after_arm_s": 5}, "duration_s": 10, "delay_ms": 1000}))
    assert p["ASTRA_ATK_MODEL"] == 5 and p["ASTRA_ATK_DLY_MS"] == 1000
    p, _ = attack_params(sc({"model": "jam_chaotic", "start": {"after_arm_s": 5}, "duration_s": 10}))
    assert p["ASTRA_ATK_MODEL"] == 7


def test_multiple_attacks_are_refused_not_ignored():
    att = {"model": "jam_denial", "start": {"after_arm_s": 5}, "duration_s": 10}
    s = Scenario.model_validate({**BASE, "attacks": [att, att]})
    with pytest.raises(ValueError, match="one attack"):
        attack_params(s)
