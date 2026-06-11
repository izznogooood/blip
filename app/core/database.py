from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _make_engine(database_url: str):
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # Allow usage across FastAPI's threadpool.
        connect_args["check_same_thread"] = False
        _ensure_sqlite_dir(database_url)
    return create_engine(database_url, connect_args=connect_args)


def _ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory for a file-based SQLite database."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return
    db_path = database_url[len(prefix):]
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create database tables for all imported models."""
    # Imported for their side effect: registering models on ``Base.metadata``.
    from app.models import cache, settings  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    with SessionLocal() as session:
        yield session
