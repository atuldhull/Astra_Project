"""Create-or-migrate DB schema for ASTRA.

Hackathon-grade migration: we don't run Alembic. Instead this script:
  1. Creates any tables that don't exist (Base.metadata.create_all)
  2. Adds individual columns that newer code expects but older DBs don't have

Idempotent — safe to run as many times as you like.

Usage:
    python -m backend.scripts.init_db
or from backend/:
    python -m scripts.init_db
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root OR backend/ — bootstrap sys.path either way.
_HERE = Path(__file__).resolve()
for p in (_HERE.parent.parent, _HERE.parent.parent.parent):  # backend/, repo-root/
    if (p / "app").exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
        break

from sqlalchemy import inspect, text

from app.db.models import Base
from app.db.session import engine


# Round-2 column additions: (table, column, ALTER TABLE clause)
ROUND2_COLUMNS: list[tuple[str, str, str]] = [
    ("detections", "extras_json", "ALTER TABLE detections ADD COLUMN extras_json TEXT"),
    ("alerts", "confirmations_json", "ALTER TABLE alerts ADD COLUMN confirmations_json TEXT"),
    ("audit_events", "prev_hash", "ALTER TABLE audit_events ADD COLUMN prev_hash VARCHAR(64)"),
    ("audit_events", "row_hash", "ALTER TABLE audit_events ADD COLUMN row_hash VARCHAR(64)"),
    # v3.0/T0.13 — soft-delete on missions; NULL means active.
    ("missions", "deleted_at", "ALTER TABLE missions ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE"),
]

# Round-2 Postgres enum value additions: (enum_type, new_value).
# Postgres enums are static — `Base.metadata.create_all` won't add new
# values to a pre-existing type. Each is wrapped in a separate transaction
# because ALTER TYPE ADD VALUE can't run inside a multi-statement
# transaction in older Postgres.
ROUND2_ENUM_VALUES: list[tuple[str, str]] = [
    ("auditeventtype", "alert_confirmation"),
    ("auditeventtype", "alert_engaged"),
    ("alertstatus", "engaged"),
]


def main() -> None:
    print("Creating any missing tables...")
    # Force-import any model modules that aren't in the package __init__ so
    # SQLAlchemy registers them on Base.metadata before create_all.
    from app.db import models as _models  # noqa: F401
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    print("\nApplying Round-2 column additions (if absent)...")
    with engine.begin() as conn:
        for table, column, ddl in ROUND2_COLUMNS:
            if not inspector.has_table(table):
                print(f"  [skip] table {table} does not exist (create_all should have caught this)")
                continue
            cols = {c["name"] for c in inspector.get_columns(table)}
            if column in cols:
                print(f"  [ok]   {table}.{column} already present")
                continue
            print(f"  [add]  {table}.{column}")
            conn.execute(text(ddl))

    print("\nApplying Round-2 enum value additions (if absent)...")
    # Postgres-only — no-op on SQLite/MySQL where enums are different.
    if engine.dialect.name == "postgresql":
        for enum_type, value in ROUND2_ENUM_VALUES:
            with engine.begin() as conn:
                # Check if value already exists in enum.
                exists = conn.execute(text("""
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = :etype AND e.enumlabel = :val
                """), {"etype": enum_type, "val": value}).first()
                if exists:
                    print(f"  [ok]   {enum_type}.{value} already present")
                    continue
                print(f"  [add]  {enum_type}.{value}")
                # Use IF NOT EXISTS via DO block to be safe on race
                conn.execute(text(f"ALTER TYPE {enum_type} ADD VALUE IF NOT EXISTS '{value}'"))

    # Repair audit-event hash chain. Re-walks every row from genesis and
    # rewrites any row whose prev_hash/row_hash doesn't match the chain
    # value. This both backfills NULL hashes (pre-Round-2 rows) AND repairs
    # rows that were chained against an incomplete predecessor (rows
    # written by the new code BEFORE the backfill ran).
    print("\nRepairing audit-event hash chain (re-walks from genesis, rewrites mismatched rows)...")
    from app.db.models import AuditEvent
    from app.db.session import SessionLocal
    from app.services.audit import GENESIS_HASH, _row_hash
    db = SessionLocal()
    try:
        rows = db.query(AuditEvent).order_by(AuditEvent.id.asc()).all()
        prev = GENESIS_HASH
        repaired = 0
        for r in rows:
            fields = {
                "event_type": r.event_type.value,
                "operator_id": r.operator_id,
                "mission_id": r.mission_id,
                "alert_id": r.alert_id,
                "payload": r.payload_json,
            }
            expected = _row_hash(prev, fields)
            if r.prev_hash != prev or r.row_hash != expected:
                r.prev_hash = prev
                r.row_hash = expected
                repaired += 1
            prev = expected
        if repaired:
            db.commit()
            print(f"  repaired {repaired} of {len(rows)} rows")
        else:
            print(f"  all {len(rows)} rows already chain-correct")
    finally:
        db.close()

    print("\nFinal table list:")
    for tname in sorted(inspect(engine).get_table_names()):
        print(f"  - {tname}")
    print("\nDone.")


if __name__ == "__main__":
    main()
