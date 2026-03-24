"""MongoDB index definitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel

from app.core.constants import TicketStatuses
from app.db.collections import DatabaseCollections

COLLECTION_INDEXES: dict[str, list[IndexModel]] = {
    DatabaseCollections.USERS: [
        IndexModel([("email", ASCENDING)], unique=True, name="users_email_unique"),
        IndexModel([("role", ASCENDING)], name="users_role_idx"),
    ],
    DatabaseCollections.MOVIES: [
        IndexModel([("title", ASCENDING)], name="movies_title_idx"),
        IndexModel([("is_active", ASCENDING)], name="movies_is_active_idx"),
    ],
    DatabaseCollections.SESSIONS: [
        IndexModel([("movie_id", ASCENDING)], name="sessions_movie_id_idx"),
        IndexModel([("start_time", ASCENDING)], name="sessions_start_time_idx"),
        IndexModel([("status", ASCENDING)], name="sessions_status_idx"),
    ],
    DatabaseCollections.TICKETS: [
        IndexModel([("user_id", ASCENDING)], name="tickets_user_id_idx"),
        IndexModel([("session_id", ASCENDING)], name="tickets_session_id_idx"),
        IndexModel(
            [
                ("session_id", ASCENDING),
                ("seat_row", ASCENDING),
                ("seat_number", ASCENDING),
            ],
            unique=True,
            partialFilterExpression={"status": TicketStatuses.PURCHASED},
            name="tickets_active_session_seat_unique",
        ),
    ],
}


def _normalize_index_key(raw_key: object) -> tuple[tuple[str, int], ...]:
    """Convert MongoDB index key definitions into a stable tuple form."""
    if isinstance(raw_key, Mapping):
        items = raw_key.items()
    else:
        items = raw_key
    return tuple((str(field), int(direction)) for field, direction in items)


def _freeze_index_option(value: Any) -> Any:
    """Convert nested index options into hashable values for comparison."""
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze_index_option(nested)) for key, nested in value.items()))
    if isinstance(value, list):
        return tuple(_freeze_index_option(item) for item in value)
    return value


def _index_signature(index_spec: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return the index characteristics that matter for idempotent creation."""
    return (
        _normalize_index_key(index_spec["key"]),
        bool(index_spec.get("unique", False)),
        _freeze_index_option(index_spec.get("partialFilterExpression")),
    )


def _find_conflicting_indexes(
    existing_indexes: Mapping[str, Mapping[str, Any]],
    desired_spec: Mapping[str, Any],
) -> list[str]:
    """Return same-key indexes whose options differ from the desired definition."""
    desired_key = _normalize_index_key(desired_spec["key"])
    desired_signature = _index_signature(desired_spec)

    return [
        name
        for name, existing_spec in existing_indexes.items()
        if name != "_id_"
        and _normalize_index_key(existing_spec["key"]) == desired_key
        and _index_signature(existing_spec) != desired_signature
    ]


async def ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    """Create configured indexes for all known collections."""
    for collection_name, indexes in COLLECTION_INDEXES.items():
        collection = database[collection_name]
        existing_indexes = await collection.index_information()
        indexes_to_create: list[IndexModel] = []

        for index in indexes:
            desired_spec = index.document

            for conflicting_index_name in _find_conflicting_indexes(existing_indexes, desired_spec):
                await collection.drop_index(conflicting_index_name)
                existing_indexes = {
                    name: spec
                    for name, spec in existing_indexes.items()
                    if name != conflicting_index_name
                }

            if any(
                _index_signature(existing_spec) == _index_signature(desired_spec)
                for existing_spec in existing_indexes.values()
            ):
                continue

            indexes_to_create.append(index)
            existing_indexes = {
                **existing_indexes,
                str(desired_spec["name"]): desired_spec,
            }

        if indexes_to_create:
            await collection.create_indexes(indexes_to_create)
