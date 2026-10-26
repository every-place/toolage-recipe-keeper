"""Database connection. SQLite on your computer; Postgres when DATABASE_URL is set."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from . import config
from .models import metadata


def normalize_url(url: str) -> str:
    """Hosted Postgres services hand out postgres:// URLs; SQLAlchemy needs the driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def database_url() -> str:
    url = config.get("DATABASE_URL")
    if url:
        return normalize_url(url)
    return f"sqlite:///{config.data_dir() / 'recipes.db'}"


_engines: dict[str, Engine] = {}


def get_engine(url: str | None = None) -> Engine:
    """Create (once per URL) an engine and the tables."""
    url = url or database_url()
    if url not in _engines:
        kwargs = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        eng = create_engine(url, **kwargs)
        if url.startswith("sqlite"):

            @event.listens_for(eng, "connect")
            def _fk_on(dbapi_conn, _):
                dbapi_conn.execute("PRAGMA foreign_keys=ON")  # SQLite has these OFF by default

        metadata.create_all(eng)
        _engines[url] = eng
    return _engines[url]
