"""
/errors endpoint — collect frontend ErrorBoundary reports.

Frontend POSTs JSON {scope, message, stack, component_stack, ts, ua}
on render-time exceptions. We log to file (no DB writes — error storms
must not amplify under fault). Operator can grep .errors.log post-incident.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/errors", tags=["errors"])

REPO_ROOT = Path(__file__).resolve().parents[3]
LOG_FILE = REPO_ROOT / ".frontend-errors.log"


class FrontendError(BaseModel):
    scope: str = Field(default="unknown", max_length=64)
    message: str = Field(default="", max_length=2048)
    stack: str | None = Field(default=None, max_length=8192)
    component_stack: str | None = Field(default=None, max_length=8192)
    ts: str | None = None
    ua: str | None = Field(default=None, max_length=512)


@router.post("")
def collect(err: FrontendError) -> dict:
    record = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        **err.model_dump(),
    }
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        # Never fail this endpoint — it's a sink, not a transaction.
        pass
    return {"received": True}
