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
]


def main() -> None:
    print("Creating any missing tables...")
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

    print("\nFinal table list:")
    for tname in sorted(inspect(engine).get_table_names()):
        print(f"  - {tname}")
    print("\nDone.")


if __name__ == "__main__":
    main()
