"""Ticket repository implementation."""

from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError

from app.adapters.mongo_adapter import MongoDocumentAdapter
from app.core.exceptions import ConflictException
from app.db.collections import DatabaseCollections
from app.repositories.base import BaseRepository
from app.utils.identifiers import to_object_id


class TicketRepository(BaseRepository):
    """Repository encapsulating access to the tickets collection."""

    @property
    def collection_name(self) -> str:
        """Return the MongoDB collection name for tickets."""
        return DatabaseCollections.TICKETS

    async def create_ticket(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a new ticket document and return the normalized result."""
        try:
            result = await self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise ConflictException("Selected seat has already been purchased.") from exc

        created = await self.collection.find_one({"_id": result.inserted_id})
        return MongoDocumentAdapter.normalize(created) or {}

    async def delete_ticket(self, ticket_id: str) -> None:
        """Delete a ticket by its identifier."""
        await self.collection.delete_one({"_id": to_object_id(ticket_id)})

    async def find_by_session_and_seat(
        self,
        session_id: str,
        seat_row: int,
        seat_number: int,
    ) -> dict[str, Any] | None:
        """Return a ticket for a specific session seat if it already exists."""
        ticket = await self.collection.find_one(
            {
                "session_id": session_id,
                "seat_row": seat_row,
                "seat_number": seat_number,
            }
        )
        return MongoDocumentAdapter.normalize(ticket)

    async def list_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """Return all tickets sold for a session."""
        cursor = self.collection.find({"session_id": session_id})
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def count_by_session(self, session_id: str) -> int:
        """Return the number of sold tickets for a session."""
        return await self.collection.count_documents({"session_id": session_id})
