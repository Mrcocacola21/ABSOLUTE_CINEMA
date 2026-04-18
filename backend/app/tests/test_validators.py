"""Unit tests for MongoDB collection validator bootstrap."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.constants import MOVIE_STATUS_VALUES, ORDER_STATUS_VALUES
from app.core.genres import SUPPORTED_GENRE_CODES
from app.db.collections import DatabaseCollections
from app.db.validators import COLLECTION_VALIDATORS, ensure_collection_validators


class FakeDatabase:
    """Minimal async database stub for validator bootstrap tests."""

    def __init__(self, existing_collection_names: list[str]) -> None:
        self._existing_collection_names = existing_collection_names
        self.created_collections: list[tuple[str, dict[str, object]]] = []
        self.commands: list[dict[str, object]] = []

    async def list_collection_names(self) -> list[str]:
        return list(self._existing_collection_names)

    async def create_collection(self, name: str, **options: object) -> None:
        self.created_collections.append((name, options))
        self._existing_collection_names.append(name)

    async def command(self, payload: dict[str, object]) -> None:
        self.commands.append(payload)


@pytest.mark.asyncio
async def test_ensure_collection_validators_creates_missing_collections() -> None:
    database = FakeDatabase(existing_collection_names=[DatabaseCollections.USERS])

    await ensure_collection_validators(database)

    created_names = [name for name, _ in database.created_collections]
    assert created_names == [
        DatabaseCollections.MOVIES,
        DatabaseCollections.SESSIONS,
        DatabaseCollections.ORDERS,
        DatabaseCollections.TICKETS,
    ]
    assert database.commands == [
        {
            "collMod": DatabaseCollections.USERS,
            **COLLECTION_VALIDATORS[DatabaseCollections.USERS],
        }
    ]


@pytest.mark.asyncio
async def test_ensure_collection_validators_updates_existing_collections() -> None:
    settings = get_settings()
    database = FakeDatabase(
        existing_collection_names=[
            DatabaseCollections.USERS,
            DatabaseCollections.MOVIES,
            DatabaseCollections.SESSIONS,
            DatabaseCollections.ORDERS,
            DatabaseCollections.TICKETS,
        ]
    )

    await ensure_collection_validators(database)

    assert database.created_collections == []
    assert len(database.commands) == 5

    sessions_command = next(
        command for command in database.commands if command["collMod"] == DatabaseCollections.SESSIONS
    )
    movies_command = next(
        command for command in database.commands if command["collMod"] == DatabaseCollections.MOVIES
    )
    orders_command = next(
        command for command in database.commands if command["collMod"] == DatabaseCollections.ORDERS
    )
    tickets_command = next(
        command for command in database.commands if command["collMod"] == DatabaseCollections.TICKETS
    )

    movie_properties = movies_command["validator"]["$jsonSchema"]["properties"]
    order_properties = orders_command["validator"]["$jsonSchema"]["properties"]
    session_validator_clauses = sessions_command["validator"]["$and"]
    ticket_validator_clauses = tickets_command["validator"]["$and"]
    session_properties = session_validator_clauses[0]["$jsonSchema"]["properties"]
    session_expr = session_validator_clauses[1]["$expr"]["$and"]
    ticket_properties = ticket_validator_clauses[0]["$jsonSchema"]["properties"]
    ticket_expr = ticket_validator_clauses[1]["$expr"]["$or"]

    assert movie_properties["status"]["enum"] == list(MOVIE_STATUS_VALUES)
    assert movie_properties["title"]["required"] == ["uk", "en"]
    assert movie_properties["description"]["required"] == ["uk", "en"]
    assert movie_properties["title"]["properties"]["uk"]["maxLength"] == 150
    assert movie_properties["description"]["properties"]["en"]["maxLength"] == 2000
    assert movie_properties["duration_minutes"]["minimum"] == 40
    assert movie_properties["duration_minutes"]["maximum"] == 360
    assert movie_properties["genres"]["items"]["enum"] == list(SUPPORTED_GENRE_CODES)
    assert movie_properties["genres"]["uniqueItems"] is True
    assert order_properties["status"]["enum"] == list(ORDER_STATUS_VALUES)
    assert session_properties["movie_id"]["bsonType"] == "string"
    assert session_properties["price"]["maximum"] == 1000
    assert session_properties["total_seats"]["minimum"] == settings.total_seats
    assert session_properties["total_seats"]["maximum"] == settings.total_seats
    assert session_properties["updated_at"]["bsonType"] == ["date", "null"]
    assert {"$gt": ["$end_time", "$start_time"]} in session_expr
    assert {"$eq": ["$total_seats", settings.total_seats]} in session_expr
    assert {"$lte": ["$available_seats", "$total_seats"]} in session_expr
    assert order_properties["tickets_count"]["minimum"] == 1
    assert order_properties["tickets_count"]["maximum"] == settings.total_seats
    assert ticket_properties["user_id"]["bsonType"] == "string"
    assert ticket_properties["order_id"]["bsonType"] == ["string", "null"]
    assert ticket_properties["session_id"]["bsonType"] == "string"
    assert ticket_properties["seat_row"]["maximum"] == settings.hall_rows_count
    assert ticket_properties["seat_number"]["maximum"] == settings.hall_seats_per_row
    assert any({"$eq": ["$status", "purchased"]} in clause["$and"] for clause in ticket_expr)
    assert any({"$eq": ["$status", "cancelled"]} in clause["$and"] for clause in ticket_expr)
