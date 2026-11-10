"""Built-in scenario packs (generated, so every parameter sweep is explicit and reviewable)."""

from __future__ import annotations

from astra.scenario import Scenario

# Thar-desert reference site (flat, featureless: the hard case for visual/terrain aids).
THAR = {"lat": 27.0, "lon": 71.0, "alt_m": 200.0}


def _base(sid: str, title: str, attacks: list[dict], leg_m: float = 2500.0) -> Scenario:
    return Scenario.model_validate({
        "id": sid,
        "title": title,
        "home": THAR,
        "mission": {"takeoff_alt_m": 30, "speed_ms": 10, "end": "land",
                    "waypoints": [{"north_m": leg_m, "east_m": 0, "alt_m": 30}]},
        "attacks": attacks,
        "time_limit_s": 900,
    })


def _start(delay: float = 20.0) -> dict:
    return {"at_waypoint": 1, "delay_s": delay}


def baseline_v1() -> list[Scenario]:
    """Single-attack sweep over all 7 models on a 2.5 km cruise leg. Attack begins 20 s into cruise."""
    out: list[Scenario] = [_base("bl1-none", "No attack (control)", [])]
    for rate in (0.25, 0.5, 1.0, 2.0, 4.0):
        for consistent in (True, False):
            tag = "c" if consistent else "n"
            out.append(_base(
                f"bl1-drag-{rate:g}-{tag}",
                f"Drag-off {rate:g} m/s east, {'consistent' if consistent else 'naive'} velocity, 90 s",
                [{"model": "spoof_drag", "start": _start(), "duration_s": 90, "rate_ms": rate,
                  "bearing_deg": 90, "consistent": consistent}]))
    for rate in (0.5, 1.0, 2.0):
        out.append(_base(
            f"bl1-dragp-{rate:g}-c",
            f"Persistent consistent drag-off {rate:g} m/s east until mission end",
            [{"model": "spoof_drag", "start": _start(), "duration_s": 3600, "rate_ms": rate,
              "bearing_deg": 90, "consistent": True}]))
    for d in (25, 100, 400):
        out.append(_base(f"bl1-jump-{d}", f"Position jump {d} m east for 90 s",
                         [{"model": "spoof_jump", "start": _start(), "duration_s": 90,
                           "north_m": 0, "east_m": d}]))
    for dur in (30, 120):
        out.append(_base(f"bl1-deny-{dur}", f"Total denial {dur} s",
                         [{"model": "jam_denial", "start": _start(), "duration_s": dur}]))
    out.append(_base("bl1-intermittent", "Intermittent jamming 4 s period, 50 % duty, 120 s",
                     [{"model": "jam_intermittent", "start": _start(), "duration_s": 120,
                       "period_s": 4, "duty": 0.5}]))
    out.append(_base("bl1-chaotic", "ArduPilot chaotic jamming model, 60 s",
                     [{"model": "jam_chaotic", "start": _start(), "duration_s": 60}]))
    out.append(_base("bl1-degrade", "Degraded: 5 sats, 8 m accuracy, 120 s",
                     [{"model": "jam_degrade", "start": _start(), "duration_s": 120,
                       "num_sats": 5, "accuracy_m": 8}]))
    for ms in (1000, 3000):
        out.append(_base(f"bl1-meacon-{ms}", f"Meaconing {ms} ms delay, 120 s",
                         [{"model": "meaconing", "start": _start(), "duration_s": 120, "delay_ms": ms}]))
    return out


PACKS = {"baseline-v1": baseline_v1}


# ── Detector-development corpora ────────────────────────────────────────────
import math as _math
import random as _random

_PASSIVE = {"optical_flow": True, "rangefinder": True, "imu": "mems"}


def _random_mission(rng: _random.Random) -> dict:
    n = rng.randint(1, 4)
    wps, (pn, pe) = [], (0.0, 0.0)
    for _ in range(n):
        brg, d = rng.uniform(0, 2 * _math.pi), rng.uniform(400, 1500)
        pn, pe = pn + d * _math.cos(brg), pe + d * _math.sin(brg)
        r = _math.hypot(pn, pe)
        if r > 2200:  # keep inside a 2.2 km radius
            pn, pe = pn * 2200 / r, pe * 2200 / r
        wps.append({"north_m": round(pn, 1), "east_m": round(pe, 1), "alt_m": rng.choice([20, 30, 40, 50])})
    return {"takeoff_alt_m": wps[0]["alt_m"], "speed_ms": rng.choice([5, 8, 10, 12, 15]),
            "end": "land", "waypoints": wps}


def _corpus_scenario(sid: str, rng: _random.Random, attacks: list[dict]) -> Scenario:
    return Scenario.model_validate({
        "id": sid, "title": sid, "home": THAR, "mission": _random_mission(rng),
        "environment": {"wind_speed_ms": rng.uniform(0, 8), "wind_dir_deg": rng.uniform(0, 359.9),
                        "wind_turbulence": rng.uniform(0, 2)},
        "sensors": _PASSIVE, "attacks": attacks, "time_limit_s": 1200,
    })


def benign_v1(n: int = 160) -> list[Scenario]:
    rng = _random.Random("benign-v1")
    return [_corpus_scenario(f"benign-v1-{i:03d}", rng, []) for i in range(n)]


def _attack_corpus(tag: str, n_geom: int) -> list[Scenario]:
    rng = _random.Random(tag)
    out = []
    for g in range(n_geom):
        for rate in (0.25, 0.5, 1.0, 2.0):
            for ramp in (0, 15, 60):
                for consistent in (True, False):
                    att = {"model": "spoof_drag", "start": {"at_waypoint": 1, "delay_s": rng.uniform(10, 40)},
                           "duration_s": 3600, "rate_ms": rate, "bearing_deg": round(rng.uniform(0, 359.9), 1),
                           "consistent": consistent, "ramp_s": ramp}
                    sid = f"{tag}-g{g}-r{rate:g}-ramp{ramp}-{'c' if consistent else 'n'}"
                    out.append(_corpus_scenario(sid, rng, [att]))
    return out


def attack_dev() -> list[Scenario]:
    return _attack_corpus("attack-dev", 2)


def attack_test() -> list[Scenario]:
    return _attack_corpus("attack-test", 4)


PACKS.update({"benign-v1": benign_v1, "attack-dev": attack_dev, "attack-test": attack_test})
