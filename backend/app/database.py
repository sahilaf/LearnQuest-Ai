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
            # Pool size: 5 + 10 ran out on 2026-09-29 once requests held
            # connections through AI calls (see release_connection). Port 6543
            # is Supabase's transaction pooler, which multiplexes many client
            # connections, so a bigger app-side pool is safe. Tunable by env.
            #
            # TCP keepalives: "SSL connection has been closed unexpectedly"
            # appeared alongside the exhaustion - idle connections dropped by
            # the network path. Keepalive probes stop that for the price of a
            # few bytes every 30s, instead of pre_ping's round trip per request.
            _engine = create_engine(
                url,
                pool_pre_ping=pre_ping,
                pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "240")),
                pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
                max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
                pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "15")),
                connect_args={
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 3,
                },
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


def release_connection(db: Session | None) -> None:
    """Hand this session's connection back to the pool before a slow await.

    Call it right before awaiting a model. A Session keeps its pooled
    connection from its first query until commit/rollback/close, so a request
    that read a row and then awaited the AI held a connection for the whole
    call - 5-20s when Gemini is over quota and the chain falls through to
    OpenRouter. Measured 2026-09-29: a handful of such requests plus normal
    page traffic exhausted the 15-connection pool, and every other request
    waited 30s and failed ("QueuePool limit of size 5 overflow 10 reached").

    Commits what is pending: at every call site that is work which should
    persist whatever the model then says (the student's message, a new
    session row). Loaded objects are expired and reload on next access, on a
    fresh checkout, after the await.
    """
    if db is None:
        return
    try:
        if db.in_transaction():
            db.commit()
    except Exception:
        db.rollback()
        raise


def database_is_configured() -> bool:
    return bool(settings.database_url)
