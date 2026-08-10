"""Shared dependencies.

The session store is a process-local singleton, which is what confines the
server to a single worker. That constraint is deliberate for a free-tier
deployment and is stated in the README.
"""

from functools import lru_cache

from fastapi import HTTPException

from backend_app.config import get_settings
from backend_app.sessions import DatasetSession, SessionNotFound, SessionStore


@lru_cache
def get_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(
        ttl_seconds=settings.session_ttl_seconds,
        max_sessions=settings.max_sessions,
    )


def session_or_404(session_id: str) -> DatasetSession:
    try:
        return get_store().get(session_id)
    except SessionNotFound as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
