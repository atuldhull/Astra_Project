"""
Chain anchor service (T1.2).

The hash-chained audit log is tamper-evident in isolation, but a
single-controlled chain has one weakness: an admin who controls both
the rows AND the verifier could rewrite history end-to-end and re-walk
the chain to produce a fresh-looking valid result.

External anchoring breaks that. Periodically we:
  1. Read the current chain tip (latest audit_events.row_hash).
  2. Append a JSON line to anchors/log.jsonl with {tip, count, ts}.
  3. (Optional Round-4 path: also commit the tip to OpenTimestamps or
     a coalition partner's API. Not in v3.0.)

Once a tip is anchored, the only way to rewrite history without breaking
the anchor file is to also rewrite EVERY anchor entry whose tip claim
references the rewritten chain — and the anchor file is append-only by
contract.

The endpoint /api/v1/anchor/* exposes:
  * status     — last anchor entry + total anchors
  * verify     — re-checks every anchor's claimed tip against the live
                 chain. ok=False means an anchor's claim no longer matches
                 the chain's actual hash at that count → tampering.

Cadence: anchor every ANCHOR_INTERVAL audit events (default 50). A
lightweight check runs at the end of every audit log_event() call —
if the count crossed a threshold since the last anchor, we anchor.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent

log = logging.getLogger("astra.anchor")

ANCHORS_DIR = Path(os.environ.get("ASTRA_ANCHORS_DIR", "D:/astra-data/anchors"))
ANCHOR_FILE = ANCHORS_DIR / "log.jsonl"
ANCHOR_INTERVAL = int(os.environ.get("ASTRA_ANCHOR_INTERVAL", "50"))
ENABLED = os.environ.get("ASTRA_ANCHOR_ENABLED", "true").lower() != "false"

_lock = threading.Lock()


# ── Read helpers ───────────────────────────────────────────────────────

@dataclass
class AnchorEntry:
    ts: str
    count: int
    tip: str
    backend: str  # "local-file" today; "opentimestamps" / "coalition" in R4

    @classmethod
    def from_dict(cls, d: dict) -> "AnchorEntry":
        return cls(ts=d["ts"], count=int(d["count"]), tip=d["tip"], backend=d.get("backend", "local-file"))

    def to_dict(self) -> dict:
        return {"ts": self.ts, "count": self.count, "tip": self.tip, "backend": self.backend}


def _read_all() -> list[AnchorEntry]:
    if not ANCHOR_FILE.exists():
        return []
    out: list[AnchorEntry] = []
    for line in ANCHOR_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(AnchorEntry.from_dict(json.loads(line)))
        except Exception as exc:
            log.warning("anchor: bad line skipped: %s", exc)
    return out


def last_anchor() -> AnchorEntry | None:
    entries = _read_all()
    return entries[-1] if entries else None


def count_anchors() -> int:
    return len(_read_all())


# ── Write path ─────────────────────────────────────────────────────────

def _write_entry(entry: AnchorEntry) -> None:
    ANCHORS_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry.to_dict(), separators=(",", ":")) + "\n"
    # Append-open + flush. We deliberately don't fsync — the audit chain
    # itself is the authoritative log; anchors are a cross-reference.
    with ANCHOR_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def _live_chain_tip(db: Session) -> tuple[int, str | None]:
    """Return (row_count, latest_row_hash)."""
    count = int(db.execute(select(func.count()).select_from(AuditEvent)).scalar_one() or 0)
    if count == 0:
        return 0, None
    tip = db.execute(
        select(AuditEvent.row_hash).order_by(AuditEvent.id.desc()).limit(1)
    ).scalar_one_or_none()
    return count, tip


def maybe_anchor(db: Session) -> AnchorEntry | None:
    """Idempotent — called from app.services.audit.log_event() after
    every commit. Anchors only if (current_count - last_anchored_count)
    >= ANCHOR_INTERVAL. Locked so concurrent ingests can't double-anchor.
    """
    if not ENABLED:
        return None
    with _lock:
        count, tip = _live_chain_tip(db)
        if count == 0 or not tip:
            return None
        last = last_anchor()
        last_count = last.count if last else 0
        if count - last_count < ANCHOR_INTERVAL:
            return None
        entry = AnchorEntry(
            ts=datetime.now(timezone.utc).isoformat(),
            count=count,
            tip=tip,
            backend="local-file",
        )
        try:
            _write_entry(entry)
            log.info("anchor: wrote count=%d tip=%s...", count, tip[:8])
            return entry
        except Exception as exc:
            log.warning("anchor: write failed: %s", exc)
            return None


def force_anchor(db: Session) -> AnchorEntry | None:
    """Manually triggered anchor (operator action via /anchor/now)."""
    if not ENABLED:
        return None
    with _lock:
        count, tip = _live_chain_tip(db)
        if count == 0 or not tip:
            return None
        entry = AnchorEntry(
            ts=datetime.now(timezone.utc).isoformat(),
            count=count,
            tip=tip,
            backend="local-file",
        )
        _write_entry(entry)
        log.info("anchor: force-anchored count=%d tip=%s...", count, tip[:8])
        return entry


# ── Verify ─────────────────────────────────────────────────────────────

def verify(db: Session) -> dict:
    """Re-check every anchor entry against the live audit chain.

    For each historical anchor, look up the audit_event with id == count
    and confirm row_hash matches the anchored tip. Any mismatch means
    history was rewritten between the anchor and now.

    Returns {ok, total, mismatches: [{count, anchored_tip, live_tip}], ...}.
    """
    if not ENABLED:
        return {"ok": False, "reason": "anchor disabled"}
    entries = _read_all()
    if not entries:
        return {"ok": True, "total": 0, "mismatches": [], "last": None}

    mismatches: list[dict] = []
    for e in entries:
        # The Nth audit event (id ordering) at anchor-time should still
        # have row_hash == e.tip. We use COUNT of rows ≤ that id, since
        # ids may not be perfectly contiguous after deletions.
        # Simpler approach: get the row whose ordinal position is e.count.
        rows = db.execute(
            select(AuditEvent.row_hash).order_by(AuditEvent.id.asc()).limit(e.count)
        ).scalars().all()
        if len(rows) < e.count:
            mismatches.append({
                "count": e.count, "ts": e.ts,
                "reason": f"chain shorter than anchor ({len(rows)} < {e.count})",
            })
            continue
        live_tip = rows[-1]
        if live_tip != e.tip:
            mismatches.append({
                "count": e.count, "ts": e.ts,
                "anchored_tip": e.tip, "live_tip": live_tip,
                "reason": "tip mismatch — chain rewritten since anchor",
            })

    return {
        "ok": len(mismatches) == 0,
        "total": len(entries),
        "mismatches": mismatches,
        "last": entries[-1].to_dict() if entries else None,
    }


def status() -> dict:
    last = last_anchor()
    return {
        "enabled": ENABLED,
        "anchor_file": str(ANCHOR_FILE),
        "interval": ANCHOR_INTERVAL,
        "total": count_anchors(),
        "last": last.to_dict() if last else None,
    }
