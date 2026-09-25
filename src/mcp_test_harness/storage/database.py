from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all persisted ORM models."""


def create_db_engine(database_url: str) -> Engine:
    """Build a SQLAlchemy engine for `database_url`.

    SQLite connections are per-thread by default, which breaks under
    FastAPI's threadpool-backed sync dependencies; `check_same_thread=False`
    disables that check (each request still gets its own `Session`).
    """
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    """Build a `Session` factory for `database_url`, creating tables if needed."""
    engine = create_db_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
