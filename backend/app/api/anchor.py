"""
/anchor — chain anchor status, force-anchor-now, verify.

GET  /anchor/status   → enabled flag, file path, total anchors, last entry
POST /anchor/now      → manually capture the current chain tip (demo trigger)
GET  /anchor/verify   → re-walks every anchor against live chain; surfaces
                        any tip mismatch that would indicate retroactive
                        history rewriting between anchor-time and now.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.anchor import force_anchor, status, verify

router = APIRouter(prefix="/anchor", tags=["anchor"])


@router.get("/status")
def anchor_status() -> dict:
    return status()


@router.post("/now")
def anchor_now(db: Session = Depends(get_db)) -> dict:
    entry = force_anchor(db)
    if entry is None:
        return {"ok": False, "reason": "anchoring disabled or chain empty"}
    return {"ok": True, "anchor": entry.to_dict()}


@router.get("/verify")
def anchor_verify(db: Session = Depends(get_db)) -> dict:
    return verify(db)
