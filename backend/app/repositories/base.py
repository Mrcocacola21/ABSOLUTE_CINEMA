"""Base repository abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from motor.motor_asyncio import AsyncIOMotorCollection

from app.db.database import mongodb_manager


class BaseRepository(ABC):
    """Base repository exposing access to its MongoDB collection."""

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """Return the MongoDB collection name used by the repository."""

    @property
    def collection(self) -> AsyncIOMotorCollection:
        """Return the Motor collection instance for the repository."""
        database = mongodb_manager.get_database()
        return database[self.collection_name]
