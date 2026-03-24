"""Session repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.core.constants import SessionStatuses
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository
from app.utils.identifiers import to_object_id


class SessionRepository(BaseRepository):
    """Repository encapsulating access to the sessions collection."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for sessions."""
        return DatabaseCollections.SESSIONS

    async def create_session(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a new session document and return the normalized result."""
        result = await self.collection.insert_one(document)
        created = await self.collection.find_one({"_id": result.inserted_id})
        return MongoDocumentAdapter.normalize(created) or {}

    async def get_by_id(self, session_id: str) -> dict[str, Any] | None:
        """Return a session document by its identifier."""
        session = await self.collection.find_one({"_id": to_object_id(session_id)})
        return MongoDocumentAdapter.normalize(session)

    async def list_by_ids(self, session_ids: list[str]) -> list[dict[str, Any]]:
        """Return sessions for the provided identifiers."""
        if not session_ids:
            return []
        cursor = self.collection.find(
            {"_id": {"$in": [to_object_id(session_id) for session_id in set(session_ids)]}}
        )
        documents = await cursor.to_list(length=len(session_ids))
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_public_schedule(
        self,
        *,
        current_time: datetime,
        movie_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return upcoming scheduled sessions for public schedule browsing."""
        query: dict[str, Any] = {
            "status": SessionStatuses.SCHEDULED,
            "start_time": {"$gt": current_time},
        }
        if movie_id:
            query["movie_id"] = movie_id

        cursor = self.collection.find(query).sort("start_time", 1)
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_all(self) -> list[dict[str, Any]]:
        """Return all sessions ordered by start time."""
        cursor = self.collection.find({}).sort("start_time", 1)
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def find_overlapping(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        exclude_session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Return an overlapping non-cancelled session if one exists."""
        query: dict[str, Any] = {
            "status": {"$ne": SessionStatuses.CANCELLED},
            "start_time": {"$lt": end_time},
            "end_time": {"$gt": start_time},
        }
        if exclude_session_id is not None:
            query["_id"] = {"$ne": to_object_id(exclude_session_id)}

        overlapping = await self.collection.find_one(query)
        return MongoDocumentAdapter.normalize(overlapping)

    async def update_session(
        self,
        session_id: str,
        *,
        updates: dict[str, Any],
        updated_at: datetime,
    ) -> dict[str, Any] | None:
        """Apply partial updates to a session and return the updated document."""
        updated = await self.collection.find_one_and_update(
            {"_id": to_object_id(session_id)},
            {"$set": {**updates, "updated_at": updated_at}},
            return_document=ReturnDocument.AFTER,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def update_session_if_editable(
        self,
        session_id: str,
        *,
        updates: dict[str, Any],
        current_time: datetime,
        updated_at: datetime,
    ) -> dict[str, Any] | None:
        """Update a session only while it is still a future scheduled session without sold seats."""
        updated = await self.collection.find_one_and_update(
            {
                "_id": to_object_id(session_id),
                "status": SessionStatuses.SCHEDULED,
                "start_time": {"$gt": current_time},
                "$expr": {"$eq": ["$available_seats", "$total_seats"]},
            },
            {"$set": {**updates, "updated_at": updated_at}},
            return_document=ReturnDocument.AFTER,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def update_status(
        self,
        session_id: str,
        *,
        status: str,
        updated_at: datetime,
    ) -> dict[str, Any] | None:
        """Update session status and return the updated document."""
        updated = await self.collection.find_one_and_update(
            {"_id": to_object_id(session_id)},
            {"$set": {"status": status, "updated_at": updated_at}},
            return_document=ReturnDocument.AFTER,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def cancel_future_scheduled_session(
        self,
        session_id: str,
        *,
        current_time: datetime,
        updated_at: datetime,
    ) -> dict[str, Any] | None:
        """Cancel a session only while it remains a future scheduled session."""
        updated = await self.collection.find_one_and_update(
            {
                "_id": to_object_id(session_id),
                "status": SessionStatuses.SCHEDULED,
                "start_time": {"$gt": current_time},
            },
            {
                "$set": {
                    "status": SessionStatuses.CANCELLED,
                    "updated_at": updated_at,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session by identifier."""
        result = await self.collection.delete_one({"_id": to_object_id(session_id)})
        return result.deleted_count == 1

    async def count_by_movie(self, movie_id: str) -> int:
        """Return the number of sessions linked to a movie."""
        return await self.collection.count_documents({"movie_id": movie_id})

    async def sync_completed_sessions(self, *, current_time: datetime, updated_at: datetime) -> int:
        """Mark sessions that have already ended as completed."""
        result = await self.collection.update_many(
            {
                "status": SessionStatuses.SCHEDULED,
                "end_time": {"$lte": current_time},
            },
            {
                "$set": {
                    "status": SessionStatuses.COMPLETED,
                    "updated_at": updated_at,
                }
            },
        )
        return result.modified_count

    async def decrement_available_seats_for_purchase(
        self,
        session_id: str,
        *,
        current_time: datetime,
        updated_at: datetime,
    ) -> bool:
        """Decrease available seats only if the session is still purchasable."""
        result = await self.collection.update_one(
            {
                "_id": to_object_id(session_id),
                "status": SessionStatuses.SCHEDULED,
                "start_time": {"$gt": current_time},
                "available_seats": {"$gt": 0},
            },
            {
                "$inc": {"available_seats": -1},
                "$set": {"updated_at": updated_at},
            },
        )
        return result.modified_count == 1

    async def increment_available_seats(
        self,
        session_id: str,
        *,
        updated_at: datetime,
    ) -> bool:
        """Restore an available seat only if the counter is still below total capacity."""
        result = await self.collection.update_one(
            {
                "_id": to_object_id(session_id),
                "$expr": {"$lt": ["$available_seats", "$total_seats"]},
            },
            {
                "$inc": {"available_seats": 1},
                "$set": {"updated_at": updated_at},
            },
        )
        return result.modified_count == 1

    async def set_available_seats(
        self,
        session_id: str,
        *,
        available_seats: int,
        updated_at: datetime,
    ) -> dict[str, Any] | None:
        """Set the exact available seats value when repairing denormalized counters."""
        updated = await self.collection.find_one_and_update(
            {
                "_id": to_object_id(session_id),
                "total_seats": {"$gte": available_seats},
            },
            {
                "$set": {
                    "available_seats": available_seats,
                    "updated_at": updated_at,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return MongoDocumentAdapter.normalize(updated)
