"""
/chat endpoint — commander Q&A over the database state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.rag import answer, status as rag_status

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=512)


class ChatOut(BaseModel):
    answer: str
    source: str
    citations: list[dict]
    llm_available: bool


@router.post("", response_model=ChatOut)
def ask(body: ChatIn, db: Session = Depends(get_db)) -> ChatOut:
    a = answer(db, body.question)
    s = rag_status()
    return ChatOut(answer=a.text, source=a.source, citations=a.citations, llm_available=s["llm_available"])


@router.get("/status")
def chat_status() -> dict:
    return rag_status()
