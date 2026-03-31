"""Unit tests for MongoDB index bootstrap."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.core.constants import TicketStatuses
from app.db.collections import DatabaseCollections
from app.db.indexes import ensure_indexes


class FakeCollection:
    """Minimal async collection stub for index bootstrap tests."""

    def __init__(self, indexes: dict[str, dict]) -> None:
        self._indexes = {name: dict(spec) for name, spec in indexes.items()}
        self.dropped_indexes: list[str] = []
        self.created_batches: list[list[str]] = []

    async def index_information(self) -> dict[str, dict]:
        return {name: dict(spec) for name, spec in self._indexes.items()}

    async def drop_index(self, name: str) -> None:
        self.dropped_indexes.append(name)
        self._indexes.pop(name, None)

    async def create_indexes(self, indexes: Iterable) -> None:
        created_names: list[str] = []
        for index in indexes:
            spec = index.document
            name = str(spec["name"])
            created_names.append(name)
            self._indexes[name] = {
                key: value
                for key, value in spec.items()
                if key != "name"
            }
            self._indexes[name]["key"] = list(spec["key"].items())
        self.created_batches.append(created_names)


class FakeDatabase:
    """Dictionary-backed async database stub."""

    def __init__(self, collections: dict[str, FakeCollection]) -> None:
        self._collections = collections

    def __getitem__(self, collection_name: str) -> FakeCollection:
        return self._collections[collection_name]


def _build_database(ticket_indexes: dict[str, dict]) -> FakeDatabase:
    return FakeDatabase(
        {
            DatabaseCollections.USERS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "ux_users_email": {"key": [("email", 1)], "unique": True},
                    "ix_users_role": {"key": [("role", 1)]},
                }
            ),
            DatabaseCollections.MOVIES: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "ix_movies_title": {"key": [("title", 1)]},
                    "ix_movies_status": {"key": [("status", 1)]},
                }
            ),
            DatabaseCollections.SESSIONS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "ix_sessions_movie_id": {"key": [("movie_id", 1)]},
                    "ix_sessions_start_time": {"key": [("start_time", 1)]},
                    "ix_sessions_status": {"key": [("status", 1)]},
                    "ix_sessions_movie_start": {"key": [("movie_id", 1), ("start_time", 1)]},
                }
            ),
            DatabaseCollections.TICKETS: FakeCollection(ticket_indexes),
        }
    )


@pytest.mark.asyncio
async def test_ensure_indexes_accepts_equivalent_legacy_index_names() -> None:
    database = _build_database(
        {
            "_id_": {"key": [("_id", 1)]},
            "ix_tickets_user_id": {"key": [("user_id", 1)]},
            "ix_tickets_session_id": {"key": [("session_id", 1)]},
            "tickets_active_session_seat_unique": {
                "key": [("session_id", 1), ("seat_row", 1), ("seat_number", 1)],
                "unique": True,
                "partialFilterExpression": {"status": TicketStatuses.PURCHASED},
            },
        }
    )

    await ensure_indexes(database)

    for collection in database._collections.values():
        assert collection.dropped_indexes == []
        assert collection.created_batches == []


@pytest.mark.asyncio
async def test_ensure_indexes_replaces_legacy_ticket_seat_unique_index() -> None:
    database = _build_database(
        {
            "_id_": {"key": [("_id", 1)]},
            "ix_tickets_user_id": {"key": [("user_id", 1)]},
            "ix_tickets_session_id": {"key": [("session_id", 1)]},
            "ux_tickets_session_seat": {
                "key": [("session_id", 1), ("seat_row", 1), ("seat_number", 1)],
                "unique": True,
            },
        }
    )

    await ensure_indexes(database)

    tickets_collection = database[DatabaseCollections.TICKETS]
    assert tickets_collection.dropped_indexes == ["ux_tickets_session_seat"]
    assert tickets_collection.created_batches == [["tickets_active_session_seat_unique"]]
