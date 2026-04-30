from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# pool sizing for the recurring "QueuePool limit reached"
# zombie state seen across  →  closes. The default 5 + 10 overflow
# is exhausted within minutes by accumulated chrome dev-tab keep-alives
# polling /audit/verify, /alerts, /health every few seconds.
#
# pool_size=20, max_overflow=40 → 60 concurrent connections, plenty for
# the single-process uvicorn + 5–10 client tabs we ever run in dev.
# pool_recycle=900 → recycle every 15 min so stale connections don't
# accumulate when Postgres drops idle ones.
# pool_pre_ping=True → catches dropped connections before checkout.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_recycle=900,
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
