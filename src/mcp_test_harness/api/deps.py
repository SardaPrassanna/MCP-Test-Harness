from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from mcp_test_harness.config import get_settings
from mcp_test_harness.storage.database import build_session_factory


def _get_or_build_session_factory(app_state: object) -> sessionmaker[Session]:
    """Lazily build and cache the app's session factory on first DB use.

    Deferred rather than built at app startup so that routes which never
    touch the database (like `/health`) never create a database file or
    connection, and so tests can set `app.state.settings` to a scratch
    database before the first request that needs one.
    """
    factory = getattr(app_state, "session_factory", None)
    if factory is None:
        settings = getattr(app_state, "settings", None) or get_settings()
        factory = build_session_factory(settings.database_url)
        app_state.session_factory = factory  # type: ignore[attr-defined]
    return factory


def get_session(request: Request) -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped `Session`.

    Commits on a clean exit, rolls back on an unhandled exception, and
    always closes the session — the route/service layer never manages
    transaction boundaries itself.
    """
    factory = _get_or_build_session_factory(request.app.state)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_session)]
