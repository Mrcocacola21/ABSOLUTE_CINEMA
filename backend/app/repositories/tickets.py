"""Ticket repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClientSession
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.constants import TICKET_BLOCKING_STATUS_VALUES, TicketStatuses
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

    async def create_ticket(
        self,
        document: dict[str, Any],
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any]:
        """Insert a new ticket document and return the normalized result."""
        try:
            result = await self.collection.insert_one(document, session=db_session)
        except DuplicateKeyError as exc:
            raise ConflictException("Selected seat is already reserved or purchased.") from exc

        created = await self.collection.find_one({"_id": result.inserted_id}, session=db_session)
        return MongoDocumentAdapter.normalize(created) or {}

    async def delete_ticket(
        self,
        ticket_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> None:
        """Delete a ticket by its identifier."""
        await self.collection.delete_one({"_id": to_object_id(ticket_id)}, session=db_session)

    async def delete_many_by_order(
        self,
        order_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> None:
        """Delete all tickets belonging to one order."""
        await self.collection.delete_many({"order_id": order_id}, session=db_session)

    async def find_by_session_and_seat(
        self,
        session_id: str,
        seat_row: int,
        seat_number: int,
        *,
        active_only: bool = True,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a blocking ticket for a specific session seat if it already exists."""
        query: dict[str, Any] = {
            "session_id": session_id,
            "seat_row": seat_row,
            "seat_number": seat_number,
        }
        if active_only:
            query["status"] = {"$in": list(TICKET_BLOCKING_STATUS_VALUES)}

        ticket = await self.collection.find_one(query, session=db_session)
        return MongoDocumentAdapter.normalize(ticket)

    async def get_by_id(
        self,
        ticket_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Return a ticket by identifier."""
        ticket = await self.collection.find_one({"_id": to_object_id(ticket_id)}, session=db_session)
        return MongoDocumentAdapter.normalize(ticket)

    async def list_by_order(
        self,
        order_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return all tickets belonging to one order."""
        cursor = self.collection.find({"order_id": order_id}, session=db_session).sort(
            [("reserved_at", 1), ("purchased_at", 1)]
        )
        documents = await cursor.to_list(length=200)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_by_session(
        self,
        session_id: str,
        *,
        active_only: bool = True,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return tickets for a session, optionally only those currently blocking seats."""
        query: dict[str, Any] = {"session_id": session_id}
        if active_only:
            query["status"] = {"$in": list(TICKET_BLOCKING_STATUS_VALUES)}

        cursor = self.collection.find(query, session=db_session).sort([("reserved_at", -1), ("purchased_at", -1)])
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_by_user(
        self,
        user_id: str,
        *,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return all tickets purchased by a user."""
        cursor = self.collection.find({"user_id": user_id}, session=db_session).sort(
            [("reserved_at", -1), ("purchased_at", -1)]
        )
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_all(self, *, db_session: AsyncIOMotorClientSession | None = None) -> list[dict[str, Any]]:
        """Return all tickets ordered by most recent purchase."""
        cursor = self.collection.find({}, session=db_session).sort([("reserved_at", -1), ("purchased_at", -1)])
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def list_expired_reserved_by_session(
        self,
        session_id: str,
        *,
        expires_before: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return reserved tickets whose hold window has elapsed for one session."""
        cursor = self.collection.find(
            {
                "session_id": session_id,
                "status": TicketStatuses.RESERVED,
                "expires_at": {"$lte": expires_before},
            },
            session=db_session,
        ).sort("expires_at", 1)
        documents = await cursor.to_list(length=500)
        return MongoDocumentAdapter.normalize_many(documents)

    async def update_status(
        self,
        ticket_id: str,
        *,
        status: str,
        updated_at: datetime,
        cancelled_at: datetime | None = None,
        purchased_at: datetime | None = None,
        expires_at: datetime | None = None,
        current_status: str | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> dict[str, Any] | None:
        """Update the status of a ticket and return the updated document."""
        set_payload: dict[str, Any] = {
            "status": status,
            "updated_at": updated_at,
        }
        update_payload: dict[str, Any] = {"$set": set_payload}
        if cancelled_at is not None:
            set_payload["cancelled_at"] = cancelled_at
        else:
            update_payload["$unset"] = {"cancelled_at": ""}
        if purchased_at is not None:
            set_payload["purchased_at"] = purchased_at
        if expires_at is not None:
            set_payload["expires_at"] = expires_at

        query: dict[str, Any] = {"_id": to_object_id(ticket_id)}
        if current_status is not None:
            query["status"] = current_status

        updated = await self.collection.find_one_and_update(
            query,
            update_payload,
            return_document=ReturnDocument.AFTER,
            session=db_session,
        )
        return MongoDocumentAdapter.normalize(updated)

    async def update_many_status_by_order(
        self,
        order_id: str,
        *,
        status: str,
        updated_at: datetime,
        cancelled_at: datetime | None = None,
        purchased_at: datetime | None = None,
        current_status: str | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> int:
        """Update all tickets in one order and return the number of modified documents."""
        set_payload: dict[str, Any] = {
            "status": status,
            "updated_at": updated_at,
        }
        update_payload: dict[str, Any] = {"$set": set_payload}
        if cancelled_at is not None:
            set_payload["cancelled_at"] = cancelled_at
        else:
            update_payload["$unset"] = {"cancelled_at": ""}
        if purchased_at is not None:
            set_payload["purchased_at"] = purchased_at

        query: dict[str, Any] = {"order_id": order_id}
        if current_status is not None:
            query["status"] = current_status

        result = await self.collection.update_many(
            query,
            update_payload,
            session=db_session,
        )
        return result.modified_count

    async def mark_reserved_by_order_purchased(
        self,
        order_id: str,
        *,
        purchased_at: datetime,
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> int:
        """Promote all reserved tickets in one order to purchased without changing seat counters."""
        result = await self.collection.update_many(
            {
                "order_id": order_id,
                "status": TicketStatuses.RESERVED,
                "expires_at": {"$gt": purchased_at},
            },
            {
                "$set": {
                    "status": TicketStatuses.PURCHASED,
                    "purchased_at": purchased_at,
                    "updated_at": updated_at,
                },
                "$unset": {"cancelled_at": ""},
            },
            session=db_session,
        )
        return result.modified_count

    async def expire_reserved_tickets_by_ids(
        self,
        ticket_ids: list[str],
        *,
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> int:
        """Mark selected still-reserved tickets as expired."""
        if not ticket_ids:
            return 0
        result = await self.collection.update_many(
            {
                "_id": {"$in": [to_object_id(ticket_id) for ticket_id in ticket_ids]},
                "status": TicketStatuses.RESERVED,
                "expires_at": {"$lte": updated_at},
            },
            {
                "$set": {
                    "status": TicketStatuses.EXPIRED,
                    "updated_at": updated_at,
                },
                "$unset": {
                    "cancelled_at": "",
                    "checked_in_at": "",
                    "purchased_at": "",
                },
            },
            session=db_session,
        )
        return result.modified_count

    async def check_in_many_by_order(
        self,
        order_id: str,
        *,
        checked_in_at: datetime,
        updated_at: datetime,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> int:
        """Mark all active unchecked tickets in an order as checked in."""
        result = await self.collection.update_many(
            {
                "order_id": order_id,
                "status": TicketStatuses.PURCHASED,
                "checked_in_at": None,
            },
            {
                "$set": {
                    "checked_in_at": checked_in_at,
                    "updated_at": updated_at,
                }
            },
            session=db_session,
        )
        return result.modified_count

    async def update_many_status_by_session(
        self,
        session_id: str,
        *,
        status: str,
        updated_at: datetime,
        cancelled_at: datetime | None = None,
        current_status: str | None = None,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> int:
        """Update all tickets in one session and return the number of modified documents."""
        set_payload: dict[str, Any] = {
            "status": status,
            "updated_at": updated_at,
        }
        update_payload: dict[str, Any] = {"$set": set_payload}
        if cancelled_at is not None:
            set_payload["cancelled_at"] = cancelled_at
        else:
            update_payload["$unset"] = {"cancelled_at": ""}

        query: dict[str, Any] = {"session_id": session_id}
        if current_status is not None:
            query["status"] = current_status

        result = await self.collection.update_many(
            query,
            update_payload,
            session=db_session,
        )
        return result.modified_count

    async def count_by_session(
        self,
        session_id: str,
        *,
        active_only: bool = True,
        db_session: AsyncIOMotorClientSession | None = None,
    ) -> int:
        """Return the number of tickets stored for a session."""
        query: dict[str, Any] = {"session_id": session_id}
        if active_only:
            query["status"] = {"$in": list(TICKET_BLOCKING_STATUS_VALUES)}
        return await self.collection.count_documents(query, session=db_session)
