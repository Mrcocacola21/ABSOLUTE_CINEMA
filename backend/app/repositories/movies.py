"""Movie repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.core.constants import MovieStatuses
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository
from app.utils.identifiers import to_object_id


class MovieRepository(BaseRepository):
    """Repository encapsulating access to the movies collection."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for movies."""
        return DatabaseCollections.MOVIES

    async def create_movie(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a new movie document and return the normalized result."""
        result = await self.collection.insert_one(document)
        created = await self.collection.find_one({"_id": result.inserted_id})
        return MongoDocumentAdapter.normalize(created) or {}

    async def update_movie(
        self,
        movie_id: str,
        updates: dict[str, Any],
        updated_at: datetime,
    ) -> dict[str, Any] | None:
        """Apply partial updates to a movie and return the new document."""
        updated = await self.collection.find_one_and_update(
            {"_id": to_object_id(movie_id)},
            {"$set": {**updates, "updated_at": updated_at}},
            return_document=ReturnDocument.AFTER,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def get_by_id(self, movie_id: str) -> dict[str, Any] | None:
        """Return a movie document by its identifier."""
        movie = await self.collection.find_one({"_id": to_object_id(movie_id)})
        return MongoDocumentAdapter.normalize(movie)

    async def delete_movie(self, movie_id: str) -> bool:
        """Delete a movie by identifier."""
        result = await self.collection.delete_one({"_id": to_object_id(movie_id)})
        return result.deleted_count == 1

    async def list_movies(self, *, active_only: bool) -> list[dict[str, Any]]:
        """Return movies ordered by title."""
        query: dict[str, Any] = {"status": MovieStatuses.ACTIVE} if active_only else {}
        cursor = self.collection.find(query).sort("title", 1)
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_by_ids(self, movie_ids: list[str]) -> list[dict[str, Any]]:
        """Return movies for the provided identifiers."""
        if not movie_ids:
            return []
        cursor = self.collection.find(
            {"_id": {"$in": [to_object_id(movie_id) for movie_id in set(movie_ids)]}}
        )
        documents = await cursor.to_list(length=len(movie_ids))
        return MongoDocumentAdapter.normalize_many(documents)
