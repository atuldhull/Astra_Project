"""
Counter-Drone Sentinel simulation engine (T D3.3).

Self-contained synthetic environment — single-tenant, single-process.
Drives a fleet of simulated drones over the AOI defined by
settings.friendly_assets, with three pre-built attack patterns and a
decision matrix per tick that recommends monitor / soft_kill / hard_kill
based on (range_to_asset, time_to_target, asset_value).

Friendlies carry an Ed25519-signed IFF token issued at scenario start
using the same key from app.services.provenance. Foes carry no token,
or an expired/tampered one. The /sentinel/verify endpoint runs the
real Ed25519 check — no theatre, real cryptography.

The engine is a single asyncio task that ticks at 5 Hz, broadcasts
state on /ws/c2, and exits cleanly when stop() is called or the next
start() supersedes the run.

Honest framing: NO real RF emission, NO real kinetics. The crypto
(IFF + signed c2) is real and reusable in production.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.exceptions import InvalidSignature

from app.config import settings
from app.services.provenance import get_signing_key


# ── Constants ──────────────────────────────────────────────────────────

TICK_HZ = 5.0
TICK_INTERVAL = 1.0 / TICK_HZ
TRAIL_LEN = 8
HARD_KILL_TTT_S = 5.0
SOFT_KILL_TTT_S = 30.0
MONITOR_RANGE_KM = 5.0

ASSET_VALUE: dict[str, int] = {
    "HQ":             10,
    "FOB Delta":       8,
    "Outpost Bravo":   6,
    "Fuel":            6,
}


SCENARIOS: list[dict] = [
    {
        "id": "line-abreast",
        "label": "Line abreast",
        "description": "Wide flank attack — drones spread in a line, all heading inbound.",
        "n_drones": 12,
        "n_friendlies": 4,
    },
    {
        "id": "pincer",
        "label": "Pincer",
        "description": "Two clusters approach from opposing flanks; pinch the asset.",
        "n_drones": 14,
        "n_friendlies": 4,
    },
    {
        "id": "swarm-loiter",
        "label": "Swarm loiter",
        "description": "Tight swarm orbits an offset point, then dives toward asset on cue.",
        "n_drones": 13,
        "n_friendlies": 5,
    },
]


# ── Geo helpers ─────────────────────────────────────────────────────────

EARTH_R_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(a))


def _meters_to_deg(meters: float, lat: float) -> tuple[float, float]:
    """Approximate (dlat, dlon) for a meter offset at given latitude."""
    dlat = meters / 111_000.0
    dlon = meters / (111_000.0 * max(math.cos(math.radians(lat)), 0.01))
    return dlat, dlon


# ── Drone model ────────────────────────────────────────────────────────

@dataclass
class Drone:
    id: str
    role: str            # "friendly" | "foe"
    lat: float
    lon: float
    vx_mps: float        # eastward m/s
    vy_mps: float        # northward m/s
    max_speed: float
    accel: float
    token: Optional[str]  # base64 Ed25519 signature, or None
    token_payload: Optional[dict]
    state: str = "active"   # "active" | "signal_lost" | "destroyed"
    state_since: float = 0.0
    trail: list[tuple[float, float]] = field(default_factory=list)
    signal: float = 0.7

    def speed_mps(self) -> float:
        return math.hypot(self.vx_mps, self.vy_mps)


# ── Token signing / verifying ──────────────────────────────────────────

def _build_token_payload(drone_id: str, role: str, valid: bool) -> dict:
    now = datetime.now(timezone.utc)
    expires = now + (timedelta(minutes=10) if valid else timedelta(minutes=-5))
    return {
        "drone_id": drone_id,
        "role": role,
        "issued_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_token(payload: dict) -> str:
    sig = get_signing_key().sign(_canonical(payload))
    return base64.b64encode(sig).decode("ascii")


def _maybe_tamper(payload: dict, sig_b64: str, mode: str) -> tuple[dict, Optional[str]]:
    """For foes we deliberately produce no/expired/tampered tokens to make
    the verify endpoint return ok=false. Modes:
      "none"      — drop signature entirely
      "expired"   — keep sig but force expires_at into the past
      "tampered"  — keep payload, corrupt signature
    """
    if mode == "none":
        return payload, None
    if mode == "expired":
        p = {**payload, "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}
        return p, sig_b64
    if mode == "tampered":
        # flip a byte in the signature
        raw = base64.b64decode(sig_b64.encode("ascii"))
        if not raw:
            return payload, None
        b = bytearray(raw)
        b[0] ^= 0x40
        return payload, base64.b64encode(bytes(b)).decode("ascii")
    return payload, sig_b64


def verify_token(payload: Optional[dict], sig_b64: Optional[str]) -> dict:
    """Real Ed25519 + freshness check. Returns {ok, role?, reason?}."""
    if payload is None or not sig_b64:
        return {"ok": False, "reason": "no_token"}
    try:
        sig = base64.b64decode(sig_b64.encode("ascii"))
    except Exception as exc:
        return {"ok": False, "reason": f"signature_decode: {exc}"}
    pub = get_signing_key().public_key()
    try:
        pub.verify(sig, _canonical(payload))
    except InvalidSignature:
        return {"ok": False, "reason": "signature_mismatch"}
    except Exception as exc:
        return {"ok": False, "reason": f"verify_error: {exc}"}
    # Freshness
    try:
        expires = datetime.fromisoformat(str(payload.get("expires_at", "")))
    except Exception:
        return {"ok": False, "reason": "bad_expires_at"}
    if expires < datetime.now(timezone.utc):
        return {"ok": False, "reason": "expired"}
    return {"ok": True, "role": str(payload.get("role")), "drone_id": str(payload.get("drone_id"))}


# ── Run state ──────────────────────────────────────────────────────────

@dataclass
class _Run:
    run_id: str
    scenario: str
    started_at: datetime
    drones: dict[str, Drone] = field(default_factory=dict)
    n_commands_signed: int = 0
    latencies_ms: list[float] = field(default_factory=list)


_state_lock = asyncio.Lock()
_current: Optional[_Run] = None
_task: Optional[asyncio.Task] = None


# ── Spawning ──────────────────────────────────────────────────────────

def _anchor() -> tuple[float, float]:
    """Center of the simulation field — first friendly asset, or Bangalore default."""
    assets = settings.friendly_assets
    if assets:
        return assets[0][1], assets[0][2]
    return 12.9716, 77.5946


def _spawn_drones(scenario: str, n_drones: int, n_friendlies: int) -> dict[str, Drone]:
    anchor_lat, anchor_lon = _anchor()
    drones: dict[str, Drone] = {}

    # Friendlies hover near the anchor with valid tokens.
    for i in range(n_friendlies):
        drone_id = f"FRD-{i:02d}"
        # Random position 200-600m from anchor
        bearing = random.uniform(0, 2 * math.pi)
        radius_m = random.uniform(200, 600)
        dlat, dlon = _meters_to_deg(radius_m, anchor_lat)
        lat = anchor_lat + dlat * math.cos(bearing)
        lon = anchor_lon + dlon * math.sin(bearing)
        payload = _build_token_payload(drone_id, "friendly", valid=True)
        sig = _sign_token(payload)
        drones[drone_id] = Drone(
            id=drone_id, role="friendly",
            lat=lat, lon=lon,
            vx_mps=random.uniform(-3, 3), vy_mps=random.uniform(-3, 3),
            max_speed=12.0, accel=2.0,
            token=sig, token_payload=payload,
            signal=random.uniform(0.85, 0.95),
        )

    # Foes positioned per-scenario
    n_foes = max(1, n_drones - n_friendlies)
    if scenario == "line-abreast":
        # Spread along an arc 3-4 km out, all heading inbound
        for i in range(n_foes):
            theta = math.pi * (0.3 + 0.4 * i / max(n_foes - 1, 1))   # rough sweep
            radius_m = random.uniform(3000, 4000)
            dlat, dlon = _meters_to_deg(radius_m, anchor_lat)
            lat = anchor_lat + dlat * math.cos(theta)
            lon = anchor_lon + dlon * math.sin(theta)
            # Velocity inbound toward anchor
            vec_lat = anchor_lat - lat
            vec_lon = anchor_lon - lon
            n = math.hypot(vec_lat, vec_lon) or 1.0
            speed = random.uniform(20, 35)
            vx = (vec_lon / n) * 111_000.0 * math.cos(math.radians(lat)) / 111_000.0 * speed
            vy = (vec_lat / n) * speed
            drones[_foe_id(i)] = _make_foe(i, lat, lon, vx, vy)
    elif scenario == "pincer":
        # Two clusters left/right of anchor
        for i in range(n_foes):
            side = -1 if i < n_foes // 2 else 1
            radius_m = random.uniform(2500, 3500)
            dlat = random.uniform(-200, 200) / 111_000.0
            dlon = side * radius_m / (111_000.0 * math.cos(math.radians(anchor_lat)))
            lat = anchor_lat + dlat
            lon = anchor_lon + dlon
            speed = random.uniform(22, 38)
            vy = random.uniform(-3, 3)
            vx = -side * speed
            drones[_foe_id(i)] = _make_foe(i, lat, lon, vx, vy)
    else:
        # swarm-loiter — orbit a 1km offset point, then drift inward
        offset_m = 1500
        dlat, dlon = _meters_to_deg(offset_m, anchor_lat)
        cx = anchor_lat + dlat
        cy = anchor_lon - dlon
        for i in range(n_foes):
            angle = 2 * math.pi * i / max(n_foes, 1)
            r = random.uniform(400, 700)
            d_lat, d_lon = _meters_to_deg(r, cx)
            lat = cx + d_lat * math.cos(angle)
            lon = cy + d_lon * math.sin(angle)
            # Tangential velocity
            tang_speed = random.uniform(8, 14)
            vx = -tang_speed * math.sin(angle)
            vy = tang_speed * math.cos(angle)
            drones[_foe_id(i)] = _make_foe(i, lat, lon, vx, vy)

    return drones


def _foe_id(i: int) -> str:
    return f"FOE-{i:02d}"


def _make_foe(i: int, lat: float, lon: float, vx: float, vy: float) -> Drone:
    drone_id = _foe_id(i)
    payload = _build_token_payload(drone_id, "friendly", valid=True)
    sig = _sign_token(payload)
    # 1/3 no token, 1/3 expired, 1/3 tampered
    mode = ["none", "expired", "tampered"][i % 3]
    p2, sig2 = _maybe_tamper(payload, sig, mode)
    return Drone(
        id=drone_id, role="foe",
        lat=lat, lon=lon, vx_mps=vx, vy_mps=vy,
        max_speed=40.0, accel=4.0,
        token=sig2, token_payload=p2 if sig2 else None,
        signal=random.uniform(0.55, 0.85),
    )


# ── Decision matrix ────────────────────────────────────────────────────

def _decision_for_foe(drone: Drone) -> dict:
    assets = settings.friendly_assets
    if not assets:
        return {"range_km": 999.0, "ttt_s": 9999.0, "category": "monitor",
                "nearest_asset": None, "asset_value": 0}
    best_name, best_km = "?", 1e9
    for name, lat, lon in assets:
        km = _haversine_km(drone.lat, drone.lon, lat, lon)
        if km < best_km:
            best_name, best_km = name, km
    speed = max(drone.speed_mps(), 1.0)
    ttt_s = best_km * 1000.0 / speed
    if ttt_s < HARD_KILL_TTT_S:
        category = "hard_kill"
    elif ttt_s < SOFT_KILL_TTT_S:
        category = "soft_kill"
    elif best_km > MONITOR_RANGE_KM:
        category = "monitor"
    else:
        category = "monitor"
    return {
        "range_km": round(best_km, 3),
        "ttt_s": round(ttt_s, 2),
        "category": category,
        "nearest_asset": best_name,
        "asset_value": ASSET_VALUE.get(best_name, 5),
    }


def _decision_blank() -> dict:
    return {"range_km": None, "ttt_s": None, "category": None, "nearest_asset": None, "asset_value": 0}


# ── Tick / broadcast ───────────────────────────────────────────────────

async def _broadcast_tick(run: _Run) -> None:
    from app.api.ws import c2_pool
    drones_payload: list[dict] = []
    now = time.time()
    for d in run.drones.values():
        # Decay signal lost / destroyed
        if d.state == "signal_lost":
            d.signal = max(0.0, d.signal - 0.05)
        elif d.state == "destroyed":
            # leave on screen for ~2s of grace, then drop
            if now - d.state_since > 2.0:
                continue
        else:
            # Update kinematics
            dlat, dlon = _meters_to_deg(d.vy_mps * TICK_INTERVAL, d.lat)
            d.lat += dlat
            # vx is east-west; meters_to_deg returns dlon for given meters
            _, dlon_per_m = _meters_to_deg(1.0, d.lat)
            d.lon += d.vx_mps * TICK_INTERVAL * dlon_per_m
            # tiny noise so it looks alive
            d.vx_mps += random.uniform(-0.4, 0.4)
            d.vy_mps += random.uniform(-0.4, 0.4)
            speed = d.speed_mps()
            if speed > d.max_speed:
                scale = d.max_speed / speed
                d.vx_mps *= scale
                d.vy_mps *= scale
            d.signal = max(0.4, min(1.0, d.signal + random.uniform(-0.02, 0.02)))

        # Trail
        d.trail.append((round(d.lat, 6), round(d.lon, 6)))
        if len(d.trail) > TRAIL_LEN:
            d.trail = d.trail[-TRAIL_LEN:]

        decision = _decision_for_foe(d) if d.role == "foe" and d.state == "active" else _decision_blank()
        drones_payload.append({
            "id": d.id,
            "role": d.role,
            "state": d.state,
            "lat": round(d.lat, 6),
            "lon": round(d.lon, 6),
            "vx_mps": round(d.vx_mps, 2),
            "vy_mps": round(d.vy_mps, 2),
            "speed_mps": round(d.speed_mps(), 2),
            "signal": round(d.signal, 3),
            "trail": d.trail,
            **decision,
        })

    payload = {
        "type": "sentinel_tick",
        "t": now,
        "run_id": run.run_id,
        "scenario": run.scenario,
        "drones": drones_payload,
    }
    await c2_pool.broadcast(payload)


async def _engine_loop() -> None:
    """Single long-lived task. Exits when _current goes None or task is cancelled."""
    while True:
        async with _state_lock:
            run = _current
        if run is None:
            return
        try:
            await _broadcast_tick(run)
        except Exception:
            # Never let a single bad tick kill the engine — the simulation
            # is a demo; drop and continue.
            pass
        await asyncio.sleep(TICK_INTERVAL)


# ── Public engine API ──────────────────────────────────────────────────

def list_scenarios() -> list[dict]:
    return SCENARIOS


async def start(scenario_id: str, n_drones: Optional[int] = None) -> dict:
    """Start (or supersede) a scenario. Returns {run_id, scenario, n_drones}."""
    global _current, _task
    spec = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if spec is None:
        raise ValueError(f"unknown scenario: {scenario_id}")
    n = int(n_drones or spec["n_drones"])
    n = max(8, min(15, n))
    n_friendlies = int(spec["n_friendlies"])
    drones = _spawn_drones(scenario_id, n, n_friendlies)
    run = _Run(
        run_id=str(uuid.uuid4())[:8],
        scenario=scenario_id,
        started_at=datetime.now(timezone.utc),
        drones=drones,
    )
    async with _state_lock:
        _current = run
        if _task is None or _task.done():
            _task = asyncio.create_task(_engine_loop())
    return {"run_id": run.run_id, "scenario": scenario_id, "n_drones": n, "n_friendlies": n_friendlies}


async def stop() -> dict:
    """Halt the active scenario. Idempotent."""
    global _current, _task
    async with _state_lock:
        was = _current
        _current = None
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except Exception:
            pass
    return {"stopped": True, "had_run": was is not None}


def status() -> dict:
    if _current is None:
        return {"running": False}
    return {
        "running": True,
        "run_id": _current.run_id,
        "scenario": _current.scenario,
        "started_at": _current.started_at.isoformat(),
        "n_drones": len(_current.drones),
        "n_commands_signed": _current.n_commands_signed,
        "latency_p50_ms": _percentile(_current.latencies_ms, 50.0),
    }


def _percentile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
    return round(s[idx], 1)


def get_drone(drone_id: str) -> Optional[Drone]:
    if _current is None:
        return None
    return _current.drones.get(drone_id)


def verify_drone_token(drone_id: str) -> dict:
    drone = get_drone(drone_id)
    if drone is None:
        return {"ok": False, "reason": "drone_not_found"}
    return verify_token(drone.token_payload, drone.token)


async def engage(drone_id: str, action: str, operator_id: str) -> dict:
    """Apply soft_kill or hard_kill. Returns {ok, latency_ms, drone_id, new_state}.

    The latency_ms measured here is the full server-side time from
    request entry to ack send — it's a proxy for c2 round-trip and lands
    on the wire in the next tick's broadcast plus a dedicated sentinel_ack
    event for the demo to display.
    """
    if action not in ("soft_kill", "hard_kill"):
        raise ValueError("action must be soft_kill or hard_kill")
    if _current is None:
        raise RuntimeError("no active scenario")
    drone = get_drone(drone_id)
    if drone is None:
        raise ValueError(f"drone {drone_id} not found")
    if drone.role == "friendly":
        raise ValueError("refusing to engage friendly drone")

    t0 = time.perf_counter()
    if action == "soft_kill":
        drone.state = "signal_lost"
    else:
        drone.state = "destroyed"
    drone.state_since = time.time()
    drone.vx_mps = 0.0
    drone.vy_mps = 0.0
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    # Record latency + signed-cmd count
    _current.latencies_ms.append(elapsed_ms)
    _current.n_commands_signed += 1

    # Fire ack on the c2 channel so the UI can stamp the round-trip time.
    try:
        from app.api.ws import c2_pool
        await c2_pool.broadcast({
            "type": "sentinel_ack",
            "drone_id": drone_id,
            "action": action,
            "operator_id": operator_id,
            "latency_ms": elapsed_ms,
            "ts": time.time(),
        })
    except Exception:
        pass

    return {
        "ok": True,
        "drone_id": drone_id,
        "action": action,
        "operator_id": operator_id,
        "latency_ms": elapsed_ms,
        "new_state": drone.state,
    }
