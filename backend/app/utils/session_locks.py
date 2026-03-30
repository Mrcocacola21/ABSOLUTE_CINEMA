"""Per-session async locks for write operations.

These locks only coordinate work inside the current backend process. They are a
practical safeguard for coursework deployments that run a single FastAPI
instance against MongoDB without cross-collection transactions.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def session_write_lock(session_id: str):
    """Serialize writes that affect the same session inside this process."""
    lock = _SESSION_LOCKS.setdefault(session_id, asyncio.Lock())
    async with lock:
        yield
