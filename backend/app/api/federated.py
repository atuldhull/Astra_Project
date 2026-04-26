"""
Read-only endpoint surfacing the federated-training JSONL log to the UI.

The `federated.orchestrator` module writes one JSON record per per-client
training step, per-round FoolsGold decision, and per-round aggregation. We
just read that file and reshape it into curves the React dashboard can plot.

Why not WebSocket-push the events as they happen?
  Because the orchestrator runs as a separate process (often on a different
  machine in a real deployment). A poll-based GET is the simplest contract:
  the dashboard polls every 2-5 seconds, gets the latest snapshot.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/federated", tags=["federated"])


# Mirrors federated.log.DEFAULT_LOG_PATH so the API and the orchestrator
# agree on the file location even when the orchestrator runs from a
# different cwd. Both honour ASTRA_FEDERATED_LOG.
def _log_path() -> Path:
    return Path(
        os.environ.get(
            "ASTRA_FEDERATED_LOG",
            "D:/astra-data/federated/run.jsonl",
        )
    )


def _read_records() -> list[dict]:
    import json
    p = _log_path()
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


@router.get("")
def federated_state() -> dict:
    """Return a single snapshot of the current federated run, shaped for
    direct rendering by the React dashboard.

    Response shape (always defined, all keys present even when empty):
        {
          "available": bool,                # log file exists & has records
          "config": { task, n_rounds, client_ids, poison_client_id, ... },
          "rounds_completed": int,
          "global_curve": [                 # per-round server-side eval
            {"round": 0, "loss": ..., "accuracy": ...},
            ...
          ],
          "client_curves": {                # per-client local-train metrics per round
            "node-0": [{"round": 1, "loss": ..., "accuracy": ...}, ...],
            ...
          },
          "foolsgold": [                    # per-round Sybil decisions
            {"round": 1, "weights": {...}, "diag": {...}},
            ...
          ],
          "raw_count": int                  # records read
        }
    """
    recs = _read_records()
    if not recs:
        return {
            "available": False,
            "config": {},
            "rounds_completed": 0,
            "global_curve": [],
            "client_curves": {},
            "foolsgold": [],
            "raw_count": 0,
        }

    config: dict = {}
    global_curve: list[dict] = []
    client_curves: dict[str, list[dict]] = {}
    foolsgold_rows: list[dict] = []
    rounds_completed = 0

    for r in recs:
        kind = r.get("kind")
        if kind == "server_start":
            # Strip the timestamp/kind keys to keep the config block clean
            config = {k: v for k, v in r.items() if k not in {"ts", "kind"}}
        elif kind == "aggregation":
            global_curve.append({
                "round": r.get("round", 0),
                **(r.get("global_eval") or {}),
                "note": r.get("note"),
            })
            rounds_completed = max(rounds_completed, int(r.get("round", 0)))
        elif kind == "client_fit":
            cid = r.get("client_id", "?")
            client_curves.setdefault(cid, []).append({
                "round": r.get("round"),
                "loss": r.get("loss"),
                "accuracy": r.get("accuracy"),
                "n_examples": r.get("n_examples"),
                "is_poison": r.get("is_poison", False),
            })
        elif kind == "foolsgold":
            foolsgold_rows.append({
                "round": r.get("round"),
                "weights": r.get("weights", {}),
                "diag": r.get("diag", {}),
            })

    return {
        "available": True,
        "config": config,
        "rounds_completed": rounds_completed,
        "global_curve": global_curve,
        "client_curves": client_curves,
        "foolsgold": foolsgold_rows,
        "raw_count": len(recs),
    }


@router.get("/raw")
def federated_raw() -> dict:
    """Escape hatch: the unprocessed JSONL records. Useful for debugging
    and for the 'export run' button."""
    return {"records": _read_records()}
