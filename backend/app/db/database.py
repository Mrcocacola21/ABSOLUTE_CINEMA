"""MongoDB connection management built on Motor."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorClientSession, AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.exceptions import DatabaseException
from app.core.logging import get_logger
from app.db.indexes import ensure_indexes
from app.db.validators import ensure_collection_validators

logger = get_logger(__name__)


class MongoDBManager:
    """Lifecycle-aware MongoDB connection manager."""

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._database: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        """Create the MongoDB client, validate connectivity, and ensure indexes."""
        if self._client and self._database:
            return

        settings = get_settings()
        try:
            self._client = AsyncIOMotorClient(settings.mongodb_uri, tz_aware=True)
            self._database = self._client[settings.mongodb_db_name]
            await self._client.admin.command("ping")
            topology = await self._client.admin.command("hello")
            replica_set_name = topology.get("setName")
            if not replica_set_name:
                raise DatabaseException(
                    "MongoDB replica set support is required for transactional booking flows. "
                    "Configure MongoDB as a replica set and include replicaSet in MONGODB_URI."
                )
            await ensure_collection_validators(self._database)
            await ensure_indexes(self._database)
            logger.info(
                "Connected to MongoDB replica set '%s', database '%s'.",
                replica_set_name,
                settings.mongodb_db_name,
            )
        except Exception as exc:  # pragma: no cover - defensive infrastructure path
            logger.exception("Failed to connect to MongoDB", exc_info=exc)
            if isinstance(exc, DatabaseException):
                raise
            raise DatabaseException("Unable to connect to MongoDB.") from exc

    async def disconnect(self) -> None:
        """Close the MongoDB client if it has been initialized."""
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed.")
        self._client = None
        self._database = None

    def get_database(self) -> AsyncIOMotorDatabase:
        """Return the active Motor database instance."""
        if self._database is None:
            raise RuntimeError("MongoDB has not been initialized. Call connect() first.")
        return self._database

    def get_client(self) -> AsyncIOMotorClient:
        """Return the active Motor client instance."""
        if self._client is None:
            raise RuntimeError("MongoDB has not been initialized. Call connect() first.")
        return self._client

    async def start_session(self) -> AsyncIOMotorClientSession:
        """Start a Motor client session for transactional work."""
        return await self.get_client().start_session()


mongodb_manager = MongoDBManager()
