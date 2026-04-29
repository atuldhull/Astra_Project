"""
/mesh — cross-agency audit witnessing endpoints (D3.4).

GET  /mesh/peers                   list registered peer agencies
GET  /mesh/feed?since_id=&limit=   read-only audit feed for peers
POST /mesh/witness                 a peer posts a witness signature
GET  /mesh/witnesses?audit_row_ids=…  fetch witnesses for a set of rows
POST /mesh/sync-demo               run the demo peers' walk + sign loop
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, MeshWitness
from app.db.session import get_db
from app.services import mesh

router = APIRouter(prefix="/mesh", tags=["mesh"])


# ── Schemas ────────────────────────────────────────────────────────────

class WitnessIn(BaseModel):
    peer_id: str = Field(..., min_length=1, max_length=64)
    audit_row_id: int = Field(..., gt=0)
    row_hash: str = Field(..., min_length=64, max_length=64)
    peer_signature_b64: str = Field(..., min_length=1, max_length=128)


class WitnessOut(BaseModel):
    id: int
    peer_id: str
    audit_row_id: int | None
    row_hash: str
    peer_signature_b64: str
    witnessed_at: str


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("/peers")
def peers() -> dict:
    return {"peers": mesh.list_peers(), **mesh.status()}


@router.get("/feed")
def feed(
    since_id: int = Query(0, ge=0, description="exclusive lower bound on AuditEvent.id"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """Read-only audit feed — caller is presumed to be a peer pulling the
    chain to re-walk locally. Returns rows in ascending id order so the
    caller's chain re-walk works deterministically."""
    rows = db.execute(
        select(AuditEvent)
        .where(AuditEvent.id > since_id)
        .order_by(AuditEvent.id.asc())
        .limit(limit)
    ).scalars().all()
    return {
        "since_id": since_id,
        "count": len(rows),
        "events": [
            {
                "id": r.id,
                "event_type": r.event_type.value if hasattr(r.event_type, "value") else str(r.event_type),
                "operator_id": r.operator_id,
                "mission_id": r.mission_id,
                "alert_id": r.alert_id,
                "payload": r.payload_json,
                "prev_hash": r.prev_hash,
                "row_hash": r.row_hash,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/witness", response_model=WitnessOut)
def post_witness(body: WitnessIn, db: Session = Depends(get_db)) -> WitnessOut:
    """A peer agency posts a signature attesting that it has independently
    re-walked the chain and reproduced row_hash. Server verifies the
    signature against the peer's registered pubkey before persisting."""
    if not mesh.verify_peer_signature(
        body.peer_id, body.audit_row_id, body.row_hash, body.peer_signature_b64,
    ):
        raise HTTPException(400, "peer signature verification failed")

    # Validate the audit row actually exists and the row_hash matches.
    audit = db.get(AuditEvent, body.audit_row_id)
    if audit is None:
        raise HTTPException(404, f"audit row {body.audit_row_id} not found")
    if audit.row_hash and audit.row_hash != body.row_hash:
        raise HTTPException(409, "row_hash mismatch — peer is witnessing a stale row")

    record = MeshWitness(
        peer_id=body.peer_id,
        audit_row_id=body.audit_row_id,
        row_hash=body.row_hash,
        peer_signature_b64=body.peer_signature_b64,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Already witnessed — return the existing row. Idempotent by design.
        existing = db.execute(
            select(MeshWitness).where(
                MeshWitness.peer_id == body.peer_id,
                MeshWitness.audit_row_id == body.audit_row_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            raise HTTPException(500, "integrity error and no prior row to return")
        record = existing
    db.refresh(record)
    return WitnessOut(
        id=record.id,
        peer_id=record.peer_id,
        audit_row_id=record.audit_row_id,
        row_hash=record.row_hash,
        peer_signature_b64=record.peer_signature_b64,
        witnessed_at=record.witnessed_at.isoformat() if record.witnessed_at else "",
    )


@router.get("/witnesses")
def get_witnesses(
    audit_row_ids: str = Query(..., description="comma-separated audit row ids"),
    db: Session = Depends(get_db),
) -> dict:
    """Fetch witnesses for a set of audit rows, grouped by row id.
    Used by the Audit page to render the per-row '0/2', '1/2', '2/2' pill."""
    try:
        ids = [int(t) for t in audit_row_ids.split(",") if t.strip()]
    except ValueError:
        raise HTTPException(400, "audit_row_ids must be a comma-separated list of integers")
    if not ids:
        return {"by_row": {}, "n_peers": len(mesh.DEMO_PEERS)}
    rows = db.execute(
        select(MeshWitness)
        .where(MeshWitness.audit_row_id.in_(ids))
        .order_by(MeshWitness.audit_row_id.asc(), MeshWitness.witnessed_at.asc())
    ).scalars().all()
    by_row: dict[int, list[dict]] = {}
    for w in rows:
        if w.audit_row_id is None:
            continue
        by_row.setdefault(w.audit_row_id, []).append({
            "peer_id": w.peer_id,
            "witnessed_at": w.witnessed_at.isoformat() if w.witnessed_at else None,
            "row_hash": w.row_hash,
        })
    return {
        "by_row": {str(k): v for k, v in by_row.items()},
        "n_peers": len(mesh.DEMO_PEERS),
    }


@router.post("/sync-demo")
def sync_demo(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    """Drive the synthetic peers through one full pull-verify-witness
    cycle. Real peers run their own loop hitting /mesh/feed and
    /mesh/witness — this endpoint exists so the demo can show the
    behavior without standing up an external process."""
    rows = db.execute(
        select(AuditEvent).order_by(AuditEvent.id.asc()).limit(limit)
    ).scalars().all()
    if not rows:
        return {"ok": True, "rows_seen": 0, "witnesses_added": 0, "skipped": 0}

    walks = mesh.peer_walk_and_verify(rows)
    added = 0
    skipped = 0
    refused = 0
    last_sync_ts = datetime.now(timezone.utc).isoformat()

    for peer_id in mesh.DEMO_PEERS:
        for w in walks:
            if not w.chain_ok:
                refused += 1
                continue
            if w.row_hash is None:
                continue
            sig = mesh.sign_as_peer(peer_id, w.audit_row_id, w.row_hash)
            existing = db.execute(
                select(MeshWitness).where(
                    MeshWitness.peer_id == peer_id,
                    MeshWitness.audit_row_id == w.audit_row_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue
            record = MeshWitness(
                peer_id=peer_id,
                audit_row_id=w.audit_row_id,
                row_hash=w.row_hash,
                peer_signature_b64=sig,
            )
            db.add(record)
            try:
                db.flush()
                added += 1
            except IntegrityError:
                db.rollback()
                skipped += 1
    db.commit()

    return {
        "ok": True,
        "rows_seen": len(rows),
        "peers": list(mesh.DEMO_PEERS),
        "witnesses_added": added,
        "skipped": skipped,
        "refused_due_to_tampering": refused,
        "last_sync_ts": last_sync_ts,
    }
