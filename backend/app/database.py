from __future__ import annotations

import os
from collections.abc import Generator
from urllib.parse import quote

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_engine = None
_Session = None


class Base(DeclarativeBase):
    pass


def _clean_database_url(raw: str) -> str:
    value = raw.strip().strip('"').strip("'")
    if value.lower().startswith("database_url="):
        value = value.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def _use_psycopg(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url[len("postgresql+psycopg2://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _quote_userinfo(url: str) -> str:
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    userinfo, hostpart = rest.rsplit("@", 1)
    if ":" in userinfo:
        user, password = userinfo.split(":", 1)
        userinfo = f"{quote(user, safe='')}:{quote(password, safe='')}"
    else:
        userinfo = quote(userinfo, safe="")
    return f"{scheme}://{userinfo}@{hostpart}"


def _acceptable(url: str) -> bool:
    try:
        parsed = make_url(url)
    except ArgumentError:
        return False
    if "@" not in url:
        return True
    hostpart = url.rsplit("@", 1)[-1]
    actual_host = hostpart.split("/")[0].split("?")[0].split(":")[0]
    return (parsed.host or "") == actual_host


def database_url() -> str:
    """Accept SQLite locally and the Postgres URL Render injects."""
    raw = _clean_database_url(os.getenv("DATABASE_URL", ""))
    if not raw:
        return "sqlite:///./customer360.db"
    if raw.startswith("sqlite"):
        return raw
    url = _use_psycopg(raw)
    if not _acceptable(url):
        url = _quote_userinfo(url)
    if not _acceptable(url):
        raise RuntimeError(
            "DATABASE_URL is set, but it is not a database URL. "
            "On Render, use the Postgres Internal Database URL. It starts with postgres://."
        )
    if "sslmode=" not in url:
        host = url.rsplit("@", 1)[-1].split("/")[0].split("?")[0]
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
