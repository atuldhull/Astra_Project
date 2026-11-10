import math

import pytest
from pydantic import ValidationError

from astra.attacks import lua_script
from astra.geo import latlon_to_ne, ne_to_latlon
from astra.packs import PACKS, baseline_v1
from astra.scenario import Scenario

BASE = {
    "id": "t-1", "title": "t", "home": {"lat": 27.0, "lon": 71.0, "alt_m": 200},
    "mission": {"waypoints": [{"north_m": 1000, "east_m": 0, "alt_m": 30}]},
}


def sc(**kw):
    return Scenario.model_validate({**BASE, **kw})


def test_scenario_hash_is_stable_and_content_sensitive():
    a, b = sc(), sc()
    assert a.content_hash() == b.content_hash()
    c = sc(mission={"waypoints": [{"north_m": 1001, "east_m": 0, "alt_m": 30}]})
    assert c.content_hash() != a.content_hash()


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        sc(colour="red")


def test_trigger_needs_exactly_one_start():
    bad = {"model": "jam_denial", "start": {"after_arm_s": 5, "at_waypoint": 1}, "duration_s": 10}
    with pytest.raises(ValidationError):
        sc(attacks=[bad])
    with pytest.raises(ValidationError):
        sc(attacks=[{"model": "jam_denial", "start": {}, "duration_s": 10}])


def test_meaconing_delay_capped_by_simulator_history():
    with pytest.raises(ValidationError):
        sc(attacks=[{"model": "meaconing", "start": {"after_arm_s": 1}, "duration_s": 10, "delay_ms": 5000}])


def test_lua_is_deterministic_and_embeds_scenario_hash():
    s = sc(attacks=[{"model": "spoof_drag", "start": {"at_waypoint": 1, "delay_s": 5}, "duration_s": 60,
                     "rate_ms": 0.5, "bearing_deg": 45, "consistent": True, "ramp_s": 20}])
    l1, l2 = lua_script(s), lua_script(s)
    assert l1 == l2
    assert s.content_hash() in l1
    assert "p5=20.0" in l1 and "code=6" in l1


def test_lua_only_writes_simulator_params():
    """Safety property: the attack script must never touch vehicle (non-SIM_) parameters."""
    s = baseline_v1()[5]
    import re
    names = re.findall(r'Parameter\("([A-Z0-9_]+)"\)', lua_script(s))
    assert names and all(n.startswith("SIM_GPS1_") for n in names)


def _drag_offset(rate, ramp, t):
    """Python mirror of the Lua drag kinematics."""
    if ramp > 0 and t < ramp:
        return rate * t * t / (2 * ramp)
    return rate * (t - ramp / 2)


@pytest.mark.parametrize("ramp", [0, 10, 60])
def test_drag_offset_is_integral_of_velocity_bias(ramp):
    rate, dt = 1.5, 0.01
    dist, t = 0.0, 0.0
    while t < 120:
        vel = rate * min(1.0, t / ramp) if ramp > 0 else rate
        dist += vel * dt
        t += dt
    assert math.isclose(dist, _drag_offset(rate, ramp, 120), rel_tol=2e-3)


def test_geo_round_trip_sub_millimetre():
    lat, lon = ne_to_latlon(27.0, 71.0, 1234.5, -987.6)
    n, e = latlon_to_ne(27.0, 71.0, lat, lon)
    assert abs(n - 1234.5) < 1e-3 and abs(e + 987.6) < 1e-3


@pytest.mark.parametrize("name", sorted(PACKS))
def test_packs_build_and_have_unique_ids(name):
    scs = PACKS[name]()
    ids = [s.id for s in scs]
    assert len(ids) == len(set(ids))


def test_existing_scenario_hashes_are_stable():
    """Signed reports reference scenario hashes: a schema change must not silently re-hash old scenarios."""
    s = PACKS["attack-test2"]()[5]
    assert s.content_hash() == "6db734196fdd5426a6a9f115d7868b659342d330e418ffa2f017bd3fc9818158"
