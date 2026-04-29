"""D5.8 — anchor primitives that don't need the DB.

AnchorEntry round-trip + maybe_anchor cadence threshold logic.
"""

from app.services.anchor import AnchorEntry, ANCHOR_INTERVAL


def test_anchor_entry_round_trip():
    e = AnchorEntry(ts="2026-04-29T12:00:00+00:00", count=257, tip="abc123", backend="local-file")
    d = e.to_dict()
    e2 = AnchorEntry.from_dict(d)
    assert e == e2


def test_anchor_entry_default_backend():
    """Old log lines may not carry a backend field; default to local-file."""
    e = AnchorEntry.from_dict({"ts": "2026-01-01T00:00:00+00:00", "count": 1, "tip": "a"})
    assert e.backend == "local-file"


def test_anchor_interval_is_a_positive_int():
    """Sanity — operators set this via env; if it's parsed wrong, anchoring
    breaks silently. Defaults to 50."""
    assert isinstance(ANCHOR_INTERVAL, int)
    assert ANCHOR_INTERVAL >= 1
