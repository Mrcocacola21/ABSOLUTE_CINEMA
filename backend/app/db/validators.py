"""MongoDB collection validator bootstrap."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.constants import MOVIE_STATUS_VALUES, ORDER_STATUS_VALUES, Roles, SessionStatuses, TicketStatuses
from app.core.genres import SUPPORTED_GENRE_CODES
from app.db.collections import DatabaseCollections

settings = get_settings()


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
                        "maxLength": 255,
                    },
                    "email": {
                        "bsonType": "string",
                        "minLength": 3,
                        "maxLength": 320,
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
                        "bsonType": "object",
                        "required": ["uk", "en"],
                        "properties": {
                            "uk": {
                                "bsonType": "string",
                                "minLength": 1,
                                "maxLength": 150,
                            },
                            "en": {
                                "bsonType": "string",
                                "minLength": 1,
                                "maxLength": 150,
                            },
                        },
                    },
                    "description": {
                        "bsonType": "object",
                        "required": ["uk", "en"],
                        "properties": {
                            "uk": {
                                "bsonType": "string",
                                "minLength": 1,
                                "maxLength": 2000,
                            },
                            "en": {
                                "bsonType": "string",
                                "minLength": 1,
                                "maxLength": 2000,
                            },
                        },
                    },
                    "duration_minutes": {
                        "bsonType": ["int", "long"],
                        "minimum": 40,
                        "maximum": 360,
                    },
                    "poster_url": {
                        "bsonType": ["string", "null"],
                        "maxLength": 512,
                    },
                    "age_rating": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                        "maxLength": 16,
                    },
                    "genres": {
                        "bsonType": "array",
                        "uniqueItems": True,
                        "items": {
                            "bsonType": "string",
                            "enum": list(SUPPORTED_GENRE_CODES),
                        },
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
                                "minimum": 0.01,
                                "maximum": 1000,
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
                                "minimum": settings.total_seats,
                                "maximum": settings.total_seats,
                            },
                            "available_seats": {
                                "bsonType": ["int", "long"],
                                "minimum": 0,
                                "maximum": settings.total_seats,
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
                            {"$eq": ["$total_seats", settings.total_seats]},
                            {"$lte": ["$available_seats", "$total_seats"]},
                        ]
                    }
                },
            ]
        },
        "validationLevel": "strict",
        "validationAction": "error",
    },
    DatabaseCollections.ORDERS: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "user_id",
                    "session_id",
                    "status",
                    "total_price",
                    "tickets_count",
                    "created_at",
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
                    "status": {
                        "enum": list(ORDER_STATUS_VALUES),
                    },
                    "total_price": {
                        "bsonType": ["int", "long", "double", "decimal"],
                        "minimum": 0.01,
                    },
                    "tickets_count": {
                        "bsonType": ["int", "long"],
                        "minimum": 1,
                        "maximum": settings.total_seats,
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
                            "order_id": {
                                "bsonType": ["string", "null"],
                            },
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
                                "maximum": settings.hall_rows_count,
                            },
                            "seat_number": {
                                "bsonType": ["int", "long"],
                                "minimum": 1,
                                "maximum": settings.hall_seats_per_row,
                            },
                            "price": {
                                "bsonType": ["int", "long", "double", "decimal"],
                                "minimum": 0.01,
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
                            "checked_in_at": {
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
                                    {"$eq": [{"$ifNull": ["$checked_in_at", None]}, None]},
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
