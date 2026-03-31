"""MongoDB collection validator bootstrap."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.constants import MOVIE_STATUS_VALUES, Roles, SessionStatuses, TicketStatuses
from app.db.collections import DatabaseCollections


COLLECTION_VALIDATORS: dict[str, dict[str, object]] = {
    DatabaseCollections.USERS: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "name",
                    "email",
                    "password_hash",
                    "role",
                    "is_active",
                    "created_at",
                ],
                "properties": {
                    "name": {
                        "bsonType": "string",
                        "minLength": 2,
                    },
                    "email": {
                        "bsonType": "string",
                        "minLength": 3,
                    },
                    "password_hash": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "role": {
                        "enum": [Roles.USER, Roles.ADMIN],
                    },
                    "is_active": {
                        "bsonType": "bool",
                    },
                    "created_at": {
                        "bsonType": "date",
                    },
                    "updated_at": {
                        "bsonType": ["date", "null"],
                    },
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
    },
    DatabaseCollections.MOVIES: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "title",
                    "description",
                    "duration_minutes",
                    "genres",
                    "status",
                    "created_at",
                ],
                "properties": {
                    "title": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "description": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "duration_minutes": {
                        "bsonType": ["int", "long"],
                        "minimum": 1,
                    },
                    "poster_url": {
                        "bsonType": ["string", "null"],
                    },
                    "age_rating": {
                        "bsonType": ["string", "null"],
                    },
                    "genres": {
                        "bsonType": "array",
                        "items": {"bsonType": "string"},
                    },
                    "status": {
                        "enum": list(MOVIE_STATUS_VALUES),
                    },
                    "created_at": {
                        "bsonType": "date",
                    },
                    "updated_at": {
                        "bsonType": ["date", "null"],
                    },
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
    },
    DatabaseCollections.SESSIONS: {
        "validator": {
            "$and": [
                {
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": [
                            "movie_id",
                            "start_time",
                            "end_time",
                            "price",
                            "status",
                            "total_seats",
                            "available_seats",
                            "created_at",
                        ],
                        "properties": {
                            "movie_id": {
                                "bsonType": "string",
                                "minLength": 1,
                            },
                            "start_time": {
                                "bsonType": "date",
                            },
                            "end_time": {
                                "bsonType": "date",
                            },
                            "price": {
                                "bsonType": ["int", "long", "double", "decimal"],
                                "minimum": 0,
                            },
                            "status": {
                                "enum": [
                                    SessionStatuses.SCHEDULED,
                                    SessionStatuses.CANCELLED,
                                    SessionStatuses.COMPLETED,
                                ],
                            },
                            "total_seats": {
                                "bsonType": ["int", "long"],
                                "minimum": 0,
                            },
                            "available_seats": {
                                "bsonType": ["int", "long"],
                                "minimum": 0,
                            },
                            "created_at": {
                                "bsonType": "date",
                            },
                            "updated_at": {
                                "bsonType": ["date", "null"],
                            },
                        },
                    }
                },
                {
                    "$expr": {
                        "$and": [
                            {"$gt": ["$end_time", "$start_time"]},
                            {"$lte": ["$available_seats", "$total_seats"]},
                        ]
                    }
                },
            ]
        },
        "validationLevel": "strict",
        "validationAction": "error",
    },
    DatabaseCollections.TICKETS: {
        "validator": {
            "$and": [
                {
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": [
                            "user_id",
                            "session_id",
                            "seat_row",
                            "seat_number",
                            "price",
                            "status",
                            "purchased_at",
                        ],
                        "properties": {
                            "user_id": {
                                "bsonType": "string",
                                "minLength": 1,
                            },
                            "session_id": {
                                "bsonType": "string",
                                "minLength": 1,
                            },
                            "seat_row": {
                                "bsonType": ["int", "long"],
                                "minimum": 1,
                            },
                            "seat_number": {
                                "bsonType": ["int", "long"],
                                "minimum": 1,
                            },
                            "price": {
                                "bsonType": ["int", "long", "double", "decimal"],
                                "minimum": 0,
                            },
                            "status": {
                                "enum": [TicketStatuses.PURCHASED, TicketStatuses.CANCELLED],
                            },
                            "purchased_at": {
                                "bsonType": "date",
                            },
                            "updated_at": {
                                "bsonType": ["date", "null"],
                            },
                            "cancelled_at": {
                                "bsonType": ["date", "null"],
                            },
                        },
                    }
                },
                {
                    "$expr": {
                        "$or": [
                            {
                                "$and": [
                                    {"$eq": ["$status", TicketStatuses.PURCHASED]},
                                    {"$eq": [{"$ifNull": ["$cancelled_at", None]}, None]},
                                ]
                            },
                            {
                                "$and": [
                                    {"$eq": ["$status", TicketStatuses.CANCELLED]},
                                    {"$ne": [{"$ifNull": ["$cancelled_at", None]}, None]},
                                ]
                            },
                        ]
                    }
                },
            ]
        },
        "validationLevel": "strict",
        "validationAction": "error",
    },
}


async def ensure_collection_validators(database: AsyncIOMotorDatabase) -> None:
    """Create or update collection validators to match the current data model."""
    existing_collection_names = set(await database.list_collection_names())

    for collection_name, options in COLLECTION_VALIDATORS.items():
        if collection_name not in existing_collection_names:
            await database.create_collection(collection_name, **options)
            existing_collection_names.add(collection_name)
            continue

        await database.command(
            {
                "collMod": collection_name,
                **options,
            }
        )
