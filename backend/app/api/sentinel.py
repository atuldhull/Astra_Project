"""
/sentinel — Counter-Drone Sentinel scenario control.

GET  /sentinel/scenarios          available pre-built scenarios
GET  /sentinel/status             current run state
POST /sentinel/start              begin (or supersede) a scenario
POST /sentinel/stop               halt the active scenario
POST /sentinel/verify/{drone_id}  Ed25519 IFF check on a drone's token
POST /sentinel/engage             apply soft_kill | hard_kill on a foe

Honest framing: this is a simulation environment. No real RF emission,
no real kinetics. The Ed25519 IFF check and the latency-stamped c2
ack channel are real and reusable.

Audit chain hooks: every start, engage, and stop writes a
weights_changed AuditEvent (reused enum to avoid migrations) with
payload {kind: "sentinel.<event>", ...}. This captures chain-of-custody
on simulated kills.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import AuditEventType
from app.db.session import get_db
from app.services import sentinel
from app.services.audit import log_event

router = APIRouter(prefix="/sentinel", tags=["sentinel"])


# ── Schemas ────────────────────────────────────────────────────────────

class StartIn(BaseModel):
    scenario: str
    n_drones: Optional[int] = Field(default=None, ge=8, le=15)


class EngageIn(BaseModel):
    drone_id: str
    action: str  # soft_kill | hard_kill
    operator_id: str = Field(..., min_length=1, max_length=64)


# ── Routes ─────────────────────────────────────────────────────────────

@router.get("/scenarios")
def list_scenarios() -> dict:
    return {"scenarios": sentinel.list_scenarios()}


@router.get("/status")
def status() -> dict:
    return sentinel.status()


@router.post("/start")
async def start(body: StartIn, db: Session = Depends(get_db)) -> dict:
    try:
        result = await sentinel.start(body.scenario, body.n_drones)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    # Audit hook
    log_event(
        db, AuditEventType.WEIGHTS_CHANGED,
        operator_id=None,
        payload={
            "kind": "sentinel.start",
            "scenario": body.scenario,
            "run_id": result["run_id"],
            "n_drones": result["n_drones"],
        },
    )
    db.commit()
    return result


@router.post("/stop")
async def stop(db: Session = Depends(get_db)) -> dict:
    result = await sentinel.stop()
    log_event(
        db, AuditEventType.WEIGHTS_CHANGED,
        operator_id=None,
        payload={"kind": "sentinel.stop", "had_run": result["had_run"]},
    )
    db.commit()
    return result


@router.post("/verify/{drone_id}")
def verify(drone_id: str) -> dict:
    return sentinel.verify_drone_token(drone_id)


@router.post("/engage")
async def engage(body: EngageIn, db: Session = Depends(get_db)) -> dict:
    try:
        result = await sentinel.engage(body.drone_id, body.action, body.operator_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    # Audit hook — this is the chain-of-custody capture for a simulated kill.
    log_event(
        db, AuditEventType.WEIGHTS_CHANGED,
        operator_id=body.operator_id,
        payload={
            "kind": "sentinel.engage",
            "drone_id": body.drone_id,
            "action": body.action,
            "latency_ms": result["latency_ms"],
            "new_state": result["new_state"],
        },
    )
    db.commit()
    return result
