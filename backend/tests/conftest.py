"""Pytest config for the v3.0/D5.8 minimal suite.

These tests are intentionally hermetic — no DB, no network, no GPU.
We exercise the *primitives* most prone to silent regression:

  * app.services.ops_metrics — path normalisation + observe + snapshot
  * app.api.audit            — _parse_event_types validation
  * app.services.anchor      — AnchorEntry round-trip + maybe_anchor cadence

A second-tier suite covering pipeline + DB-backed flows would need a
postgres test container; deferred until the QueuePool zombie state is
proven gone in practice.
"""

import os
import sys
from pathlib import Path

# Make `from app.* import ...` resolve when pytest runs from the repo root.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Suppress noisy warmup paths if anything imports app.main transitively.
os.environ.setdefault("ASTRA_AUTH_ENABLED", "0")
