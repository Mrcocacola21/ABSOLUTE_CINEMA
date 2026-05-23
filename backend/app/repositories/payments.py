"""Payment repository implementation."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.core.exceptions import ConflictException
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository
from app.utils.identifiers import is_valid_object_id, to_object_id


class PaymentRepository(BaseRepository):
    """Repository encapsulating access to the payments collection."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for payments."""
        return DatabaseCollections.PAYMENTS

    async def create_payment(
        self,
        document: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        """Insert a payment document and return the normalized result."""
        try:
            result = await self.collection.insert_one(document, session=db_session)
        except DuplicateKeyError as exc:
            raise ConflictException("Payment idempotency or provider reference is already in use.") from exc

        created = await self.collection.find_one({"_id": result.inserted_id}, session=db_session)
        return MongoDocumentAdapter.normalize(created) or {}

    async def get_by_id(
        self,
        payment_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a payment by its identifier."""
        payment = await self.collection.find_one({"_id": to_object_id(payment_id)}, session=db_session)
        return MongoDocumentAdapter.normalize(payment)

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a payment by its client or service idempotency key."""
        payment = await self.collection.find_one({"idempotency_key": idempotency_key}, session=db_session)
        return MongoDocumentAdapter.normalize(payment)

    async def get_by_provider_payment_id(
        self,
        *,
        provider: str,
        provider_payment_id: str,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a payment by provider-side payment identifier."""
        payment = await self.collection.find_one(
            {
                "provider": provider,
                "provider_payment_id": provider_payment_id,
            },
            session=db_session,
        )
        return MongoDocumentAdapter.normalize(payment)

    async def list_by_order(
        self,
        order_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return payments linked to one order."""
        cursor = self.collection.find({"order_id": order_id}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=100)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_by_user(
        self,
        user_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return payments linked to one user."""
        cursor = self.collection.find({"user_id": user_id}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_by_status(
        self,
        status: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return payments matching one lifecycle status."""
        cursor = self.collection.find({"status": status}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_admin_payments(
        self,
        *,
        status: str | None = None,
        provider: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return payments for the protected admin workspace."""
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if provider:
            query["provider"] = provider

        normalized_search = search.strip() if search else ""
        if normalized_search:
            escaped = re.escape(normalized_search)
            search_conditions: list[dict[str, Any]] = [
                {"order_id": {"$regex": escaped, "$options": "i"}},
                {"user_id": {"$regex": escaped, "$options": "i"}},
                {"provider": {"$regex": escaped, "$options": "i"}},
                {"provider_payment_id": {"$regex": escaped, "$options": "i"}},
                {"idempotency_key": {"$regex": escaped, "$options": "i"}},
            ]
            if is_valid_object_id(normalized_search):
                search_conditions.append({"_id": to_object_id(normalized_search)})
            query["$or"] = search_conditions

        cursor = (
            self.collection.find(query, session=db_session)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        documents = await cursor.to_list(length=limit)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_admin_payments_for_report(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 5000,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return payment rows included in the admin financial report period."""
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

    async def update_payment(
        self,
        payment_id: str,
        *,
        updates: dict[str, Any],
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Apply partial updates to a payment and return the updated document."""
        try:
            updated = await self.collection.find_one_and_update(
                {"_id": to_object_id(payment_id)},
                {"$set": {**updates, "updated_at": updated_at}},
                return_document=ReturnDocument.AFTER,
                session=db_session,
            )
        except DuplicateKeyError as exc:
            raise ConflictException("Payment provider reference is already in use.") from exc
        return MongoDocumentAdapter.normalize(updated)

    async def update_status(
        self,
        payment_id: str,
        *,
        status: str,
        updated_at: datetime,
        provider_payment_id: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        current_status: str | None = None,
        current_statuses: set[str] | tuple[str, ...] | list[str] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Update payment status and important status metadata."""
        updates: dict[str, Any] = {
            "status": status,
            "failure_code": failure_code,
            "failure_message": failure_message,
        }
        if provider_payment_id is not None:
            updates["provider_payment_id"] = provider_payment_id
        query: dict[str, Any] = {"_id": to_object_id(payment_id)}
        if current_status is not None:
            query["status"] = current_status
        if current_statuses is not None:
            query["status"] = {"$in": list(current_statuses)}

        try:
            updated = await self.collection.find_one_and_update(
                query,
                {"$set": {**updates, "updated_at": updated_at}},
                return_document=ReturnDocument.AFTER,
                session=db_session,
            )
        except DuplicateKeyError as exc:
            raise ConflictException("Payment provider reference is already in use.") from exc
        return MongoDocumentAdapter.normalize(updated)
