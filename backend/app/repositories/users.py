"""User repository implementation."""

from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.core.exceptions import ConflictException
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository
from app.utils.identifiers import to_object_id


class UserRepository(BaseRepository):
    """Repository encapsulating access to the users collection."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for users."""
        return DatabaseCollections.USERS

    async def create_user(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a user document and return the normalized result."""
        try:
            result = await self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise ConflictException("A user with this email already exists.") from exc

        created = await self.collection.find_one({"_id": result.inserted_id})
        return MongoDocumentAdapter.normalize(created) or {}

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Return a user document by email address."""
        user = await self.collection.find_one({"email": email.lower()})
        return MongoDocumentAdapter.normalize(user)

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Return a user document by its identifier."""
        user = await self.collection.find_one({"_id": to_object_id(user_id)})
        return MongoDocumentAdapter.normalize(user)
