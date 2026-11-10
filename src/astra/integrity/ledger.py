"""Append-only, hash-chained JSONL ledger.

row_hash = sha256( prev_hash_ascii || canonical_json({seq, event, data}) )
genesis prev_hash = "0" * 64

Anyone holding the file can re-walk it. Editing, deleting, inserting or
reordering any row breaks every hash after it. The chain tip is what gets
anchored externally (see astra.integrity.anchor), because a local chain alone
can be rewritten wholesale by whoever controls the file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from astra.integrity.canonical import canonical_bytes

GENESIS = "0" * 64


def row_hash(prev_hash: str, seq: int, event: str, data: Any) -> str:
    h = hashlib.sha256()
    h.update(prev_hash.encode("ascii"))
    h.update(canonical_bytes({"seq": seq, "event": event, "data": data}))
    return h.hexdigest()


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    rows: int
    tip: str
    broken_at: int | None = None
    reason: str = "ok"


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _rows(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="ascii") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def tip(self) -> tuple[int, str]:
        seq, h = -1, GENESIS
        for r in self._rows():
            seq, h = r["seq"], r["hash"]
        return seq, h

    def append(self, event: str, data: Any) -> dict[str, Any]:
        last_seq, prev = self.tip()
        seq = last_seq + 1
        row = {"seq": seq, "event": event, "data": data, "prev": prev,
               "hash": row_hash(prev, seq, event, data)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="ascii") as f:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        return row

    def verify(self) -> ChainCheck:
        prev, n = GENESIS, 0
        for expected_seq, r in enumerate(self._rows()):
            n += 1
            if r.get("seq") != expected_seq:
                return ChainCheck(False, n, prev, expected_seq, "sequence gap or reorder")
            if r.get("prev") != prev:
                return ChainCheck(False, n, prev, expected_seq, "prev_hash mismatch")
            if row_hash(prev, r["seq"], r["event"], r["data"]) != r.get("hash"):
                return ChainCheck(False, n, prev, expected_seq, "row_hash mismatch")
            prev = r["hash"]
        return ChainCheck(True, n, prev)
