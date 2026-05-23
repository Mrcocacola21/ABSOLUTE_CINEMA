"""Payment attempt repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.core.exceptions import ConflictException
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository
from app.utils.identifiers import to_object_id


class PaymentAttemptRepository(BaseRepository):
    """Repository encapsulating access to payment attempt records."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for payment attempts."""
        return DatabaseCollections.PAYMENT_ATTEMPTS

    async def create_attempt(
        self,
        document: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        """Insert a payment attempt document and return the normalized result."""
        try:
            result = await self.collection.insert_one(document, session=db_session)
        except DuplicateKeyError as exc:
            raise ConflictException("Payment attempt provider reference is already in use.") from exc

        created = await self.collection.find_one({"_id": result.inserted_id}, session=db_session)
        return MongoDocumentAdapter.normalize(created) or {}

    async def get_by_id(
        self,
        attempt_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a payment attempt by its identifier."""
        attempt = await self.collection.find_one({"_id": to_object_id(attempt_id)}, session=db_session)
        return MongoDocumentAdapter.normalize(attempt)

    async def list_by_payment(
        self,
        payment_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return attempts linked to one payment."""
        cursor = self.collection.find({"payment_id": payment_id}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=100)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_by_order(
        self,
        order_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return attempts linked to one order."""
        cursor = self.collection.find({"order_id": order_id}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=100)
        return MongoDocumentAdapter.normalize_many(documents)

    async def update_attempt(
        self,
        attempt_id: str,
        *,
        updates: dict[str, Any],
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Apply partial updates to a payment attempt and return it."""
        try:
            updated = await self.collection.find_one_and_update(
                {"_id": to_object_id(attempt_id)},
                {"$set": {**updates, "updated_at": updated_at}},
                return_document=ReturnDocument.AFTER,
                session=db_session,
            )
        except DuplicateKeyError as exc:
            raise ConflictException("Payment attempt provider reference is already in use.") from exc
        return MongoDocumentAdapter.normalize(updated)

    async def update_status(
        self,
        attempt_id: str,
        *,
        status: str,
        updated_at: datetime,
        provider_attempt_id: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Update payment attempt status and important status metadata."""
        updates: dict[str, Any] = {
            "status": status,
            "error_code": error_code,
            "error_message": error_message,
        }
        if provider_attempt_id is not None:
            updates["provider_attempt_id"] = provider_attempt_id
        if response_payload_snapshot is not None:
            updates["response_payload_snapshot"] = response_payload_snapshot
        return await self.update_attempt(
            attempt_id,
            updates=updates,
            updated_at=updated_at,
            db_session=db_session,
        )
