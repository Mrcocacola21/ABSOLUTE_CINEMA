"""Payment security audit event repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository


class PaymentAuditEventRepository(BaseRepository):
    """Repository for append-only payment security audit records."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for payment audit events."""
        return DatabaseCollections.PAYMENT_AUDIT_EVENTS

    async def create_event(
        self,
        document: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        """Insert an audit event and return the normalized document."""
        result = await self.collection.insert_one(document, session=db_session)
        created = await self.collection.find_one({"_id": result.inserted_id}, session=db_session)
        return MongoDocumentAdapter.normalize(created) or {}

    async def list_by_payment(
        self,
        payment_id: str,
        *,
        limit: int = 100,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return audit events linked to one payment, newest first."""
        cursor = (
            self.collection.find({"payment_id": payment_id}, session=db_session)
            .sort("created_at", -1)
            .limit(limit)
        )
        documents = await cursor.to_list(length=limit)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_recent(
        self,
        *,
        limit: int = 100,
        action: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent audit events for operational inspection."""
        query: dict[str, Any] = {}
        if action is not None:
            query["action"] = action
        if since is not None:
            query["created_at"] = {"$gte": since}

        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        documents = await cursor.to_list(length=limit)
        return MongoDocumentAdapter.normalize_many(documents)
