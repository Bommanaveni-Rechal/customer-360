from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_engine = None
_Session = None


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    """Accept SQLite locally and the Postgres URL Render injects."""
    url = os.getenv("DATABASE_URL", "sqlite:///./customer360.db").strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("sqlite") or "sslmode=" in url:
        return url
    host = url.split("@")[-1].split("/")[0].split("?")[0]
    external = "." in host and "localhost" not in host and not host.startswith("127.")
    if external:
        url += "&" if "?" in url else "?"
        url += "sslmode=require"
    return url


def get_engine():
    global _engine, _Session
    if _engine is None:
        url = database_url()
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            kwargs["pool_size"] = 5
            kwargs["max_overflow"] = 2
        _engine = create_engine(url, **kwargs)
        _Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def SessionLocal() -> Session:
    get_engine()
    assert _Session is not None
    return _Session()


def reset_engine() -> None:
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


def ensure_action_columns() -> None:
    """Add action-log columns on a database created before ownership and outcomes."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    if "actions" not in inspect(engine).get_table_names():
        return
    present = {column["name"] for column in inspect(engine).get_columns("actions")}
    additions = {
        "owner": "VARCHAR(80) DEFAULT ''",
        "due_on": "DATE",
        "priority": "VARCHAR(16) DEFAULT ''",
        "result": "VARCHAR(40) DEFAULT ''",
        "risk_before": "VARCHAR(16) DEFAULT ''",
        "risk_after": "VARCHAR(16) DEFAULT ''",
        "nba_before": "VARCHAR(180) DEFAULT ''",
        "nba_after": "VARCHAR(180) DEFAULT ''",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in present:
                connection.execute(text(f"ALTER TABLE actions ADD COLUMN {name} {column_type}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
