"""Shared MongoDB transaction helper for critical booking flows."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
from pymongo.write_concern import WriteConcern

from app.db.database import mongodb_manager


@asynccontextmanager
async def mongo_transaction() -> AsyncIterator[AsyncIOMotorClientSession]:
    """Run a block inside a MongoDB multi-document transaction."""
    async with await mongodb_manager.start_session() as db_session:
        async with db_session.start_transaction(
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
            read_preference=ReadPreference.PRIMARY,
        ):
            yield db_session
