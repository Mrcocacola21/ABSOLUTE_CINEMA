"""Refund repository implementation."""

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


class RefundRepository(BaseRepository):
    """Repository encapsulating access to refunds."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for refunds."""
        return DatabaseCollections.REFUNDS

    async def create_refund(
        self,
        document: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        """Insert a refund document and return the normalized result."""
        try:
            result = await self.collection.insert_one(document, session=db_session)
        except DuplicateKeyError as exc:
            raise ConflictException("Refund provider reference is already in use.") from exc

        created = await self.collection.find_one({"_id": result.inserted_id}, session=db_session)
        return MongoDocumentAdapter.normalize(created) or {}

    async def get_by_id(
        self,
        refund_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a refund by its identifier."""
        refund = await self.collection.find_one({"_id": to_object_id(refund_id)}, session=db_session)
        return MongoDocumentAdapter.normalize(refund)

    async def list_by_payment(
        self,
        payment_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return refunds linked to one payment."""
        cursor = self.collection.find({"payment_id": payment_id}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=100)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_by_order(
        self,
        order_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return refunds linked to one order."""
        cursor = self.collection.find({"order_id": order_id}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=100)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_admin_refunds_for_report(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 5000,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return refund rows included in the admin financial report period."""
        query: dict[str, Any] = {}
        created_at_filter: dict[str, datetime] = {}
        if date_from is not None:
            created_at_filter["$gte"] = date_from
        if date_to is not None:
            created_at_filter["$lte"] = date_to
        if created_at_filter:
            query["created_at"] = created_at_filter

        cursor = self.collection.find(query, session=db_session).sort("created_at", -1).limit(limit)
        documents = await cursor.to_list(length=limit)
        return MongoDocumentAdapter.normalize_many(documents)

    async def get_by_provider_refund_id(
        self,
        *,
        provider: str,
        provider_refund_id: str,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a refund by provider-side refund identifier."""
        refund = await self.collection.find_one(
            {
                "provider": provider,
                "provider_refund_id": provider_refund_id,
            },
            session=db_session,
        )
        return MongoDocumentAdapter.normalize(refund)

    async def update_refund(
        self,
        refund_id: str,
        *,
        updates: dict[str, Any],
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Apply partial updates to a refund and return it."""
        try:
            updated = await self.collection.find_one_and_update(
                {"_id": to_object_id(refund_id)},
                {"$set": {**updates, "updated_at": updated_at}},
                return_document=ReturnDocument.AFTER,
                session=db_session,
            )
        except DuplicateKeyError as exc:
            raise ConflictException("Refund provider reference is already in use.") from exc
        return MongoDocumentAdapter.normalize(updated)

    async def update_status(
        self,
        refund_id: str,
        *,
        status: str,
        updated_at: datetime,
        provider_refund_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        response_payload_snapshot: dict[str, Any] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Update refund status and important status metadata."""
        updates: dict[str, Any] = {
            "status": status,
            "failure_code": failure_code,
            "failure_message": failure_message,
        }
        if provider_refund_id is not None:
            updates["provider_refund_id"] = provider_refund_id
        if response_payload_snapshot is not None:
            updates["response_payload_snapshot"] = response_payload_snapshot
        return await self.update_refund(
            refund_id,
            updates=updates,
            updated_at=updated_at,
            db_session=db_session,
        )
