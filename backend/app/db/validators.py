"""MongoDB collection validator bootstrap."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.constants import (
    MOVIE_STATUS_VALUES,
    ORDER_STATUS_VALUES,
    PAYMENT_ATTEMPT_STATUS_VALUES,
    PAYMENT_STATUS_VALUES,
    PAYMENT_WEBHOOK_PROCESSING_STATUS_VALUES,
    REFUND_STATUS_VALUES,
    Roles,
    SessionStatuses,
    TICKET_STATUS_VALUES,
    TicketStatuses,
)
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
                    "poster_file_url": {
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
                    "expires_at": {
                        "bsonType": ["date", "null"],
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
                                "enum": list(TICKET_STATUS_VALUES),
                            },
                            "reserved_at": {
                                "bsonType": ["date", "null"],
                            },
                            "expires_at": {
                                "bsonType": ["date", "null"],
                            },
                            "purchased_at": {
                                "bsonType": ["date", "null"],
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
                                    {"$eq": ["$status", TicketStatuses.RESERVED]},
                                    {"$eq": [{"$ifNull": ["$purchased_at", None]}, None]},
                                    {"$eq": [{"$ifNull": ["$cancelled_at", None]}, None]},
                                    {"$eq": [{"$ifNull": ["$checked_in_at", None]}, None]},
                                    {"$ne": [{"$ifNull": ["$reserved_at", None]}, None]},
                                    {"$ne": [{"$ifNull": ["$expires_at", None]}, None]},
                                ]
                            },
                            {
                                "$and": [
                                    {"$eq": ["$status", TicketStatuses.PURCHASED]},
                                    {"$ne": [{"$ifNull": ["$purchased_at", None]}, None]},
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
                            {
                                "$and": [
                                    {"$eq": ["$status", TicketStatuses.EXPIRED]},
                                    {"$eq": [{"$ifNull": ["$purchased_at", None]}, None]},
                                    {"$eq": [{"$ifNull": ["$cancelled_at", None]}, None]},
                                    {"$eq": [{"$ifNull": ["$checked_in_at", None]}, None]},
                                    {"$ne": [{"$ifNull": ["$expires_at", None]}, None]},
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
    DatabaseCollections.PAYMENTS: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "order_id",
                    "user_id",
                    "amount_minor",
                    "currency",
                    "status",
                    "provider",
                    "idempotency_key",
                    "created_at",
                ],
                "properties": {
                    "order_id": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "user_id": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "amount_minor": {
                        "bsonType": ["int", "long"],
                        "minimum": 1,
                    },
                    "currency": {
                        "bsonType": "string",
                        "pattern": "^[A-Z]{3}$",
                    },
                    "status": {
                        "enum": list(PAYMENT_STATUS_VALUES),
                    },
                    "provider": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 64,
                    },
                    "provider_payment_id": {
                        "bsonType": ["string", "null"],
                        "maxLength": 255,
                    },
                    "idempotency_key": {
                        "bsonType": "string",
                        "minLength": 8,
                        "maxLength": 128,
                    },
                    "failure_code": {
                        "bsonType": ["string", "null"],
                        "maxLength": 128,
                    },
                    "failure_message": {
                        "bsonType": ["string", "null"],
                        "maxLength": 1000,
                    },
                    "metadata": {
                        "bsonType": ["object", "null"],
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
    DatabaseCollections.PAYMENT_ATTEMPTS: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "payment_id",
                    "order_id",
                    "provider",
                    "status",
                    "created_at",
                ],
                "properties": {
                    "payment_id": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "order_id": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "provider": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 64,
                    },
                    "status": {
                        "enum": list(PAYMENT_ATTEMPT_STATUS_VALUES),
                    },
                    "provider_attempt_id": {
                        "bsonType": ["string", "null"],
                        "maxLength": 255,
                    },
                    "request_payload_snapshot": {
                        "bsonType": ["object", "null"],
                    },
                    "response_payload_snapshot": {
                        "bsonType": ["object", "null"],
                    },
                    "error_code": {
                        "bsonType": ["string", "null"],
                        "maxLength": 128,
                    },
                    "error_message": {
                        "bsonType": ["string", "null"],
                        "maxLength": 1000,
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
    DatabaseCollections.PAYMENT_WEBHOOK_EVENTS: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "provider",
                    "event_type",
                    "signature_verified",
                    "payload_hash",
                    "processing_status",
                    "created_at",
                ],
                "properties": {
                    "provider": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 64,
                    },
                    "provider_event_id": {
                        "bsonType": ["string", "null"],
                        "maxLength": 255,
                    },
                    "event_type": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 128,
                    },
                    "signature_verified": {
                        "bsonType": "bool",
                    },
                    "payload_hash": {
                        "bsonType": "string",
                        "minLength": 16,
                        "maxLength": 128,
                    },
                    "payload_snapshot": {
                        "bsonType": ["object", "null"],
                    },
                    "processing_status": {
                        "enum": list(PAYMENT_WEBHOOK_PROCESSING_STATUS_VALUES),
                    },
                    "processed_at": {
                        "bsonType": ["date", "null"],
                    },
                    "error_message": {
                        "bsonType": ["string", "null"],
                        "maxLength": 1000,
                    },
                    "payment_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                    },
                    "order_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                    },
                    "refund_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
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
    DatabaseCollections.PAYMENT_AUDIT_EVENTS: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "action",
                    "actor_type",
                    "created_at",
                ],
                "properties": {
                    "action": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 128,
                    },
                    "actor_type": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 32,
                    },
                    "actor_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                        "maxLength": 255,
                    },
                    "payment_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                    },
                    "order_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                    },
                    "refund_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                    },
                    "webhook_event_id": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                    },
                    "provider": {
                        "bsonType": ["string", "null"],
                        "minLength": 1,
                        "maxLength": 64,
                    },
                    "old_status": {
                        "bsonType": ["string", "null"],
                        "maxLength": 128,
                    },
                    "new_status": {
                        "bsonType": ["string", "null"],
                        "maxLength": 128,
                    },
                    "reason": {
                        "bsonType": ["string", "null"],
                        "maxLength": 500,
                    },
                    "safe_context": {
                        "bsonType": ["object", "null"],
                    },
                    "created_at": {
                        "bsonType": "date",
                    },
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
    },
    DatabaseCollections.REFUNDS: {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "payment_id",
                    "order_id",
                    "user_id",
                    "amount_minor",
                    "currency",
                    "status",
                    "provider",
                    "reason",
                    "requested_by",
                    "created_at",
                ],
                "properties": {
                    "payment_id": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "order_id": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "user_id": {
                        "bsonType": "string",
                        "minLength": 1,
                    },
                    "amount_minor": {
                        "bsonType": ["int", "long"],
                        "minimum": 1,
                    },
                    "currency": {
                        "bsonType": "string",
                        "pattern": "^[A-Z]{3}$",
                    },
                    "status": {
                        "enum": list(REFUND_STATUS_VALUES),
                    },
                    "provider": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 64,
                    },
                    "provider_refund_id": {
                        "bsonType": ["string", "null"],
                        "maxLength": 255,
                    },
                    "reason": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 500,
                    },
                    "requested_by": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 255,
                    },
                    "request_payload_snapshot": {
                        "bsonType": ["object", "null"],
                    },
                    "response_payload_snapshot": {
                        "bsonType": ["object", "null"],
                    },
                    "failure_code": {
                        "bsonType": ["string", "null"],
                        "maxLength": 128,
                    },
                    "failure_message": {
                        "bsonType": ["string", "null"],
                        "maxLength": 1000,
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
