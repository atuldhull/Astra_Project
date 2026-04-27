from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, AuditEventType


GENESIS_HASH = "0" * 64


def _canonicalize(payload: Any) -> str:
    """Stable JSON for hashing: sorted keys, no spaces, ensure_ascii."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _row_hash(prev_hash: str, fields: dict) -> str:
    """SHA-256 of (prev_hash || canonical_json(fields))."""
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(_canonicalize(fields).encode("utf-8"))
    return h.hexdigest()


def latest_hash(db: Session) -> str:
    """Return the row_hash of the most-recent audit event, or genesis."""
    last = db.execute(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    ).scalar_one_or_none()
    if last is None or not last.row_hash:
        return GENESIS_HASH
    return last.row_hash


def log_event(
    db: Session,
    event_type: AuditEventType,
    *,
    operator_id: str | None = None,
    mission_id: int | None = None,
    alert_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append an immutable audit event with hash-chain link to the previous
    row. Caller is responsible for db.commit().

    The hash covers everything semantically meaningful (event type,
    operators, ids, payload). Re-hashing the chain later verifies that no
    row has been retroactively edited.
    """
    prev = latest_hash(db)
    fields = {
        "event_type": event_type.value,
        "operator_id": operator_id,
        "mission_id": mission_id,
        "alert_id": alert_id,
        "payload": payload,
    }
    row_hash = _row_hash(prev, fields)
    event = AuditEvent(
        event_type=event_type,
        operator_id=operator_id,
        mission_id=mission_id,
        alert_id=alert_id,
        payload_json=payload,
        prev_hash=prev,
        row_hash=row_hash,
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """Walk the entire audit log and confirm the hash chain is unbroken.
    Returns {"ok": bool, "checked": N, "broken_at_id": int|None}.

    Used by the frontend's Audit page to display a green "chain verified"
    badge and to surface which row, if any, was tampered with.
    """
    rows = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().all()
    prev = GENESIS_HASH
    for r in rows:
        if r.prev_hash and r.prev_hash != prev:
            return {"ok": False, "checked": r.id, "broken_at_id": r.id, "reason": "prev_hash_mismatch"}
        fields = {
            "event_type": r.event_type.value,
            "operator_id": r.operator_id,
            "mission_id": r.mission_id,
            "alert_id": r.alert_id,
            "payload": r.payload_json,
        }
        expected = _row_hash(prev, fields)
        if r.row_hash and r.row_hash != expected:
            return {"ok": False, "checked": r.id, "broken_at_id": r.id, "reason": "row_hash_mismatch"}
        prev = r.row_hash or expected
    return {"ok": True, "checked": len(rows), "broken_at_id": None}
