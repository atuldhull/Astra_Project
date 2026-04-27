"""
/chat endpoint — commander Q&A over the database state.

Round-3 add-ons:
  * mission_id is now part of the request — every turn is persisted in
    chat_messages tied to that mission. Each user turn AND ASTRA reply
    is stored, so a future page-mount can rebuild the thread.
  * GET /chat/thread?mission_id=N → returns the persisted thread.
  * POST /chat/note → free-form note attached to a mission, surfaced in
    later 'details of mission #N' briefings.
"""

from __future__ import annotations

import json as _json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, Mission
from app.db.session import get_db
from app.services.rag import answer, status as rag_status

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=512)
    mission_id: int | None = None
    operator_id: str | None = Field(default=None, max_length=64)


class ChatOut(BaseModel):
    answer: str
    source: str
    citations: list[dict]
    llm_available: bool


class ChatMessageOut(BaseModel):
    id: int
    mission_id: int | None
    role: str
    text: str
    source: str | None
    citations: list[dict]
    operator_id: str | None
    created_at: str


class NoteIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    mission_id: int = Field(..., gt=0)
    operator_id: str | None = Field(default=None, max_length=64)


@router.post("", response_model=ChatOut)
def ask(body: ChatIn, db: Session = Depends(get_db)) -> ChatOut:
    a = answer(db, body.question, mission_id=body.mission_id, operator_id=body.operator_id)
    s = rag_status()
    return ChatOut(answer=a.text, source=a.source, citations=a.citations, llm_available=s["llm_available"])


@router.get("/status")
def chat_status() -> dict:
    return rag_status()


@router.get("/thread", response_model=list[ChatMessageOut])
def get_thread(
    mission_id: int | None = Query(default=None, description="If null, returns un-scoped messages."),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ChatMessageOut]:
    stmt = select(ChatMessage)
    if mission_id is not None:
        stmt = stmt.where(ChatMessage.mission_id == mission_id)
    else:
        stmt = stmt.where(ChatMessage.mission_id.is_(None))
    stmt = stmt.order_by(ChatMessage.created_at.asc()).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [_serialize(r) for r in rows]


@router.post("/note", response_model=ChatMessageOut)
def post_note(body: NoteIn, db: Session = Depends(get_db)) -> ChatMessageOut:
    if db.get(Mission, body.mission_id) is None:
        raise HTTPException(404, f"Mission #{body.mission_id} not found")
    msg = ChatMessage(
        mission_id=body.mission_id, role="user", text=body.text.strip(),
        source="note", operator_id=body.operator_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _serialize(msg)


def _serialize(m: ChatMessage) -> ChatMessageOut:
    cites: list[dict] = []
    if m.citations_json:
        try:
            cites = _json.loads(m.citations_json)
        except Exception:
            pass
    return ChatMessageOut(
        id=m.id,
        mission_id=m.mission_id,
        role=m.role,
        text=m.text,
        source=m.source,
        citations=cites,
        operator_id=m.operator_id,
        created_at=m.created_at.isoformat() if m.created_at else "",
    )
