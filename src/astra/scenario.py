"""Scenario schema (v1).

A scenario = where (home), what the drone is asked to do (mission), the
environment, and an attack timeline. Scenarios are plain YAML/JSON, hashed
canonically, so a result is bound to exactly what was tested.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from astra.integrity.canonical import sha256_obj

SCHEMA_VERSION = 1


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Home(_Strict):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt_m: float = Field(description="Ground altitude AMSL at home (m)")
    heading_deg: float = Field(0.0, ge=0, lt=360)


class Waypoint(_Strict):
    """Offset from home in metres (north, east) and altitude above home."""
    north_m: float
    east_m: float
    alt_m: float = Field(gt=0)


class Mission(_Strict):
    takeoff_alt_m: float = Field(30.0, gt=0)
    waypoints: list[Waypoint] = Field(min_length=1)
    speed_ms: float = Field(10.0, gt=0, le=40)
    end: Literal["land", "rtl", "loiter"] = "land"


class Environment(_Strict):
    wind_speed_ms: float = Field(0.0, ge=0, le=25)
    wind_dir_deg: float = Field(0.0, ge=0, lt=360)
    wind_turbulence: float = Field(0.0, ge=0, le=5)


class Trigger(_Strict):
    """When an attack starts: seconds after arming, or after reaching a waypoint index."""
    after_arm_s: float | None = Field(None, ge=0)
    at_waypoint: int | None = Field(None, ge=1)
    delay_s: float = Field(0.0, ge=0)

    @model_validator(mode="after")
    def _one(self):
        if (self.after_arm_s is None) == (self.at_waypoint is None):
            raise ValueError("set exactly one of after_arm_s / at_waypoint")
        return self


class _Attack(_Strict):
    start: Trigger
    duration_s: float = Field(gt=0, le=3600)


class JamDenial(_Attack):
    """Barrage jamming: receiver loses lock completely."""
    model: Literal["jam_denial"] = "jam_denial"


class JamIntermittent(_Attack):
    """Pulsed/sweeping jammer: lock flickers with a duty cycle."""
    model: Literal["jam_intermittent"] = "jam_intermittent"
    period_s: float = Field(4.0, gt=0.2, le=120)
    duty: float = Field(0.5, gt=0, lt=1, description="fraction of each period without lock")


class JamChaotic(_Attack):
    """ArduPilot's built-in jamming model: random sat counts, accuracies, position/velocity jumps."""
    model: Literal["jam_chaotic"] = "jam_chaotic"


class JamDegrade(_Attack):
    """Partial / narrow-band jamming: lock kept but few satellites and poor accuracy."""
    model: Literal["jam_degrade"] = "jam_degrade"
    num_sats: int = Field(5, ge=0, le=30)
    accuracy_m: float = Field(8.0, gt=0, le=500)


class SpoofJump(_Attack):
    """Naive spoofer: position steps by an offset."""
    model: Literal["spoof_jump"] = "spoof_jump"
    north_m: float
    east_m: float


class SpoofDrag(_Attack):
    """Drag-off spoofer: reported position walks away from truth at a constant rate.

    consistent=True also biases reported velocity by the same rate (a careful
    spoofer). consistent=False leaves velocity true (a sloppy spoofer, whose
    position/velocity mismatch is a detection cue).
    """
    model: Literal["spoof_drag"] = "spoof_drag"
    rate_ms: float = Field(gt=0, le=30)
    bearing_deg: float = Field(ge=0, lt=360)
    consistent: bool = True
    ramp_s: float = Field(
        0.0, ge=0, le=600,
        description="seconds to ease the velocity bias in (0 = instant step). A careful spoofer ramps "
                    "slowly so the onset hides under IMU noise; detectors must be judged against this.",
    )
    hold_after_s: float | None = Field(
        None, ge=0, description="stop growing the offset after this many seconds (hold it)"
    )


class Meaconing(_Attack):
    """Record-and-replay: receiver reports where the drone was `delay_ms` ago."""
    model: Literal["meaconing"] = "meaconing"
    delay_ms: int = Field(gt=0, le=3500, description="limited by the simulator's 20-sample history")


Attack = Annotated[
    Union[JamDenial, JamIntermittent, JamChaotic, JamDegrade, SpoofJump, SpoofDrag, Meaconing],
    Field(discriminator="model"),
]


class Sensors(_Strict):
    """What the airframe carries. Extra sensors are passive witnesses: logged, not fused,
    unless the vendor's own params tell the EKF to use them."""
    optical_flow: bool = False
    rangefinder: bool = False
    imu: Literal["ideal", "mems"] = Field(
        "mems", description="ideal = SITL default (near-perfect). mems = per-seed bias + vibration noise"
    )
    flow_noise: Literal["ideal", "degraded"] = Field(
        "ideal", description="ideal = SITL flow (good texture everywhere). degraded = 2-5x noise, +-5% scale "
                             "error, 100-300 ms latency (poor texture / cheap sensor / imperfect calibration)"
    )
    gps: Literal["ideal", "typical"] = Field(
        "typical", description="ideal = SITL default (perfect position). typical = single-frequency "
                               "receiver: ~1 m Gauss-Markov position error, ~0.08 m/s velocity noise"
    )


class Expectation(_Strict):
    goal_radius_m: float = Field(15.0, gt=0)
    geofence_radius_m: float = Field(3000.0, gt=0)
    allowed_outcomes: list[str] = Field(
        default_factory=lambda: ["success", "safe_abort"],
        description="success | safe_abort | diverted | flyaway | crash | timeout",
    )


class Scenario(_Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,63}$")
    title: str
    description: str = ""
    vehicle: Literal["copter"] = "copter"
    home: Home
    mission: Mission
    environment: Environment = Environment()
    sensors: Sensors = Sensors()
    attacks: list[Attack] = Field(default_factory=list, max_length=8)
    expect: Expectation = Expectation()
    time_limit_s: float = Field(600.0, gt=10, le=7200)

    def content_hash(self) -> str:
        d = self.model_dump(mode="json")
        # Fields added after schema v1 are omitted at their default, so existing scenarios keep
        # the exact hashes recorded in earlier signed reports.
        if d["sensors"].get("flow_noise") == "ideal":
            del d["sensors"]["flow_noise"]
        return sha256_obj(d)

    def goal_offset(self) -> tuple[float, float]:
        wp = self.mission.waypoints[-1]
        return wp.north_m, wp.east_m

    def path_length_m(self) -> float:
        pts = [(0.0, 0.0)] + [(w.north_m, w.east_m) for w in self.mission.waypoints]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
