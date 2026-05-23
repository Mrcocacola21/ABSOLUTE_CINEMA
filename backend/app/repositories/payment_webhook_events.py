"""Payment webhook event repository implementation."""

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


class PaymentWebhookEventRepository(BaseRepository):
    """Repository encapsulating access to raw payment webhook event records."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for payment webhook events."""
        return DatabaseCollections.PAYMENT_WEBHOOK_EVENTS

    async def create_event(
        self,
        document: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        """Insert a webhook event and return the normalized document."""
        try:
            result = await self.collection.insert_one(document, session=db_session)
        except DuplicateKeyError as exc:
            raise ConflictException("Payment webhook event has already been received.") from exc

        created = await self.collection.find_one({"_id": result.inserted_id}, session=db_session)
        return MongoDocumentAdapter.normalize(created) or {}

    async def get_by_id(
        self,
        event_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a webhook event by local identifier."""
        event = await self.collection.find_one({"_id": to_object_id(event_id)}, session=db_session)
        return MongoDocumentAdapter.normalize(event)

    async def get_by_provider_event_id(
        self,
        *,
        provider: str,
        provider_event_id: str,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a webhook event by provider-side event identifier."""
        event = await self.collection.find_one(
            {
                "provider": provider,
                "provider_event_id": provider_event_id,
            },
            session=db_session,
        )
        return MongoDocumentAdapter.normalize(event)

    async def update_processing_status(
        self,
        event_id: str,
        *,
        processing_status: str,
        updated_at: datetime,
        processed_at: datetime | None = None,
        error_message: str | None = None,
        payment_id: str | None = None,
        order_id: str | None = None,
        refund_id: str | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Update webhook processing state and return the updated event."""
        updates: dict[str, Any] = {
            "processing_status": processing_status,
            "updated_at": updated_at,
            "error_message": error_message,
        }
        if processed_at is not None:
            updates["processed_at"] = processed_at
        if payment_id is not None:
            updates["payment_id"] = payment_id
        if order_id is not None:
            updates["order_id"] = order_id
        if refund_id is not None:
            updates["refund_id"] = refund_id
        updated = await self.collection.find_one_and_update(
            {"_id": to_object_id(event_id)},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
            session=db_session,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def list_by_payment_context(
        self,
        *,
        payment_id: str,
        order_id: str,
        provider: str,
        provider_payment_id: str | None = None,
        provider_refund_ids: list[str] | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return webhook rows linked to a payment through explicit ids or safe provider references."""
        conditions: list[dict[str, Any]] = [
            {"payment_id": payment_id},
            {"order_id": order_id},
        ]
        if provider_payment_id:
            conditions.extend(
                [
                    {
                        "provider": provider,
                        "payload_snapshot.payment.provider_payment_id": provider_payment_id,
                    },
                    {
                        "provider": provider,
                        "payload_snapshot.payment.id": provider_payment_id,
                    },
                ]
            )
        for provider_refund_id in provider_refund_ids or []:
            conditions.extend(
                [
                    {
                        "provider": provider,
                        "payload_snapshot.refund.provider_refund_id": provider_refund_id,
                    },
                    {
                        "provider": provider,
                        "payload_snapshot.refund.id": provider_refund_id,
                    },
                ]
            )

        cursor = self.collection.find({"$or": conditions}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=100)
        return MongoDocumentAdapter.normalize_many(documents)
