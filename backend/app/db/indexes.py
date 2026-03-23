"""MongoDB index definitions."""

from __future__ import annotations

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


async def ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    """Create configured indexes for all known collections."""
    ticket_indexes = await database[DatabaseCollections.TICKETS].index_information()
    if "tickets_session_seat_unique" in ticket_indexes:
        await database[DatabaseCollections.TICKETS].drop_index("tickets_session_seat_unique")

    for collection_name, indexes in COLLECTION_INDEXES.items():
        await database[collection_name].create_indexes(indexes)
