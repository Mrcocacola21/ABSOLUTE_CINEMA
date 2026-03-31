"""Order repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo import ReturnDocument

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository
from app.utils.identifiers import to_object_id


class OrderRepository(BaseRepository):
    """Repository encapsulating access to the orders collection."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for orders."""
        return DatabaseCollections.ORDERS

    async def create_order(
        self,
        document: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        """Insert a new order document and return the normalized result."""
        result = await self.collection.insert_one(document, session=db_session)
        created = await self.collection.find_one({"_id": result.inserted_id}, session=db_session)
        return MongoDocumentAdapter.normalize(created) or {}

    async def build_order_id(self) -> str:
        """Generate a new order identifier before the document is inserted."""
        return str(ObjectId())

    async def get_by_id(
        self,
        order_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return an order by its identifier."""
        order = await self.collection.find_one({"_id": to_object_id(order_id)}, session=db_session)
        return MongoDocumentAdapter.normalize(order)

    async def list_by_user(
        self,
        user_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return orders belonging to one user, newest first."""
        cursor = self.collection.find({"user_id": user_id}, session=db_session).sort("created_at", -1)
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, Any],
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Apply partial updates to an order and return the updated document."""
        updated = await self.collection.find_one_and_update(
            {"_id": to_object_id(order_id)},
            {"$set": {**updates, "updated_at": updated_at}},
            return_document=ReturnDocument.AFTER,
            session=db_session,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def delete_order(
        self,
        order_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> bool:
        """Delete an order by identifier."""
        result = await self.collection.delete_one({"_id": to_object_id(order_id)}, session=db_session)
        return result.deleted_count == 1
