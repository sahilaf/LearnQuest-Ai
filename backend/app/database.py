"""SQLAlchemy engine, session and Base.

SHARED FILE - change only by agreement (plan.md 2.4).

The engine is created lazily so the app still boots with no DATABASE_URL set.
That lets Members 1, 2 and 4 build against the API before Member 3 finishes Supabase.
"""

from collections.abc import Generator

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_engine = None
_SessionLocal: sessionmaker | None = None


class Base(DeclarativeBase):
    """Base class for every model. Import this in app/models/*.py."""


def get_engine():
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
                "and fill in the Supabase connection string (see plan.md 8.1)."
            )
        url = settings.database_url
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]

        if url.startswith("sqlite"):
            _engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                future=True,
            )
        else:
            # pool_pre_ping sends a test query before handing out any pooled
            # connection. Against Supabase's pooler that is a full round trip on
            # EVERY request: measured 2026-09-22 at ~105 ms, paid even by
            # requests that then do no database work at all.
            #
            # Recycling well inside the pooler's idle timeout gets most of the
            # safety for none of the cost - a connection is retired on age
            # rather than tested on use. If you start seeing "server closed the
            # connection unexpectedly", set DB_PRE_PING=true and it goes back to
            # the old behaviour in one line.
            pre_ping = os.getenv("DB_PRE_PING", "false").strip().lower() in {
                "1",
                "true",
                "yes",
            }
            _engine = create_engine(
                url,
                pool_pre_ping=pre_ping,
                pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "240")),
                pool_size=5,
                max_overflow=10,
                future=True,
            )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, future=True
        )
    return _SessionLocal


def get_db() -> Generator[Session | None, None, None]:
    """FastAPI dependency. Usage: db: Session | None = Depends(get_db)"""
    if not database_is_configured():
        yield None
        return
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def database_is_configured() -> bool:
    return bool(settings.database_url)
