"""
Tiny JSONL telemetry sink shared by the Flower server, strategy, and clients.

Rationale: a single append-only file at a known location is the cheapest way
to pass per-round metrics from the federated subprocesses (which have no DB
session) to the FastAPI backend, which exposes them at /api/v1/federated.
The frontend Federated page polls that endpoint and replots curves.

Each line is one JSON object with at minimum:
    {"ts": "2026-04-26T12:00:00Z", "round": 3, "kind": "client_fit",
     "client_id": "node-2", ...}

Kinds:
    server_start    — server boot, includes config snapshot
    client_register — a client connected for the first time
    client_fit      — a client returned trained params for round R
                      (loss, num_examples, optional local val_acc)
    foolsgold       — per-round FoolsGold weights + diagnostics
    aggregation     — global model aggregated for round R, with eval metric
    server_done     — final round complete
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from astra_paths import FEDERATED_LOG

# Default log path. Overridable via ASTRA_FEDERATED_LOG env so the
# orchestrator can sandbox different runs.
DEFAULT_LOG_PATH = Path(os.environ.get("ASTRA_FEDERATED_LOG") or FEDERATED_LOG)

_lock = threading.Lock()


def log_path() -> Path:
    return DEFAULT_LOG_PATH


def append(record: dict) -> None:
    """Atomic-ish append of one JSON record. Adds a UTC timestamp if missing."""
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def reset() -> None:
    """Truncate the log. Called by the demo orchestrator at start of a run
    so dashboards don't bleed metrics from a previous experiment."""
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        p.write_text("", encoding="utf-8")


def read_all() -> list[dict]:
    """Read every record. Cheap because the file is small (a few rounds × few
    clients). FastAPI handler calls this on every request — fine."""
    p = log_path()
    if not p.exists():
        return []
    out: list[dict] = []
    with _lock:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out
