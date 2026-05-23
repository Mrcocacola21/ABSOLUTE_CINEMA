"""MongoDB index definitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel

from app.core.constants import PaymentStatuses, TICKET_BLOCKING_STATUS_VALUES
from app.db.collections import DatabaseCollections

COLLECTION_INDEXES: dict[str, list[IndexModel]] = {
    DatabaseCollections.USERS: [
        IndexModel([("email", ASCENDING)], unique=True, name="users_email_unique"),
        IndexModel([("role", ASCENDING)], name="users_role_idx"),
    ],
    DatabaseCollections.MOVIES: [
        IndexModel([("title.uk", ASCENDING)], name="movies_title_uk_idx"),
        IndexModel([("status", ASCENDING)], name="movies_status_idx"),
    ],
    DatabaseCollections.SESSIONS: [
        IndexModel([("movie_id", ASCENDING)], name="sessions_movie_id_idx"),
        IndexModel([("start_time", ASCENDING)], name="sessions_start_time_idx"),
        IndexModel([("status", ASCENDING)], name="sessions_status_idx"),
    ],
    DatabaseCollections.ORDERS: [
        IndexModel([("user_id", ASCENDING)], name="orders_user_id_idx"),
        IndexModel([("session_id", ASCENDING)], name="orders_session_id_idx"),
        IndexModel([("status", ASCENDING)], name="orders_status_idx"),
    ],
    DatabaseCollections.TICKETS: [
        IndexModel([("user_id", ASCENDING)], name="tickets_user_id_idx"),
        IndexModel([("order_id", ASCENDING)], name="tickets_order_id_idx"),
        IndexModel([("session_id", ASCENDING)], name="tickets_session_id_idx"),
        IndexModel([("status", ASCENDING)], name="tickets_status_idx"),
        IndexModel([("expires_at", ASCENDING)], name="tickets_expires_at_idx"),
        IndexModel(
            [
                ("session_id", ASCENDING),
                ("seat_row", ASCENDING),
                ("seat_number", ASCENDING),
            ],
            unique=True,
            partialFilterExpression={"status": {"$in": list(TICKET_BLOCKING_STATUS_VALUES)}},
            name="tickets_active_session_seat_unique",
        ),
    ],
    DatabaseCollections.PAYMENTS: [
        IndexModel([("order_id", ASCENDING)], name="payments_order_id_idx"),
        IndexModel([("user_id", ASCENDING)], name="payments_user_id_idx"),
        IndexModel([("status", ASCENDING)], name="payments_status_idx"),
        IndexModel([("created_at", ASCENDING)], name="payments_created_at_idx"),
        IndexModel([("idempotency_key", ASCENDING)], unique=True, name="payments_idempotency_key_unique"),
        IndexModel(
            [("provider", ASCENDING), ("provider_payment_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"provider_payment_id": {"$type": "string"}},
            name="payments_provider_payment_id_unique",
        ),
        IndexModel(
            [("order_id", ASCENDING), ("provider", ASCENDING)],
            unique=True,
            partialFilterExpression={
                "status": {
                    "$in": [
                        PaymentStatuses.CREATED,
                        PaymentStatuses.PENDING,
                        PaymentStatuses.REQUIRES_ACTION,
                        PaymentStatuses.SUCCEEDED,
                    ]
                }
            },
            name="payments_active_order_provider_unique",
        ),
    ],
    DatabaseCollections.PAYMENT_ATTEMPTS: [
        IndexModel([("payment_id", ASCENDING)], name="payment_attempts_payment_id_idx"),
        IndexModel([("order_id", ASCENDING)], name="payment_attempts_order_id_idx"),
        IndexModel([("status", ASCENDING)], name="payment_attempts_status_idx"),
        IndexModel(
            [("provider", ASCENDING), ("provider_attempt_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"provider_attempt_id": {"$type": "string"}},
            name="payment_attempts_provider_attempt_id_unique",
        ),
    ],
    DatabaseCollections.PAYMENT_WEBHOOK_EVENTS: [
        IndexModel([("provider", ASCENDING)], name="payment_webhook_events_provider_idx"),
        IndexModel([("payment_id", ASCENDING)], name="payment_webhook_events_payment_id_idx"),
        IndexModel([("order_id", ASCENDING)], name="payment_webhook_events_order_id_idx"),
        IndexModel([("refund_id", ASCENDING)], name="payment_webhook_events_refund_id_idx"),
        IndexModel([("processing_status", ASCENDING)], name="payment_webhook_events_processing_status_idx"),
        IndexModel([("created_at", ASCENDING)], name="payment_webhook_events_created_at_idx"),
        IndexModel(
            [("provider", ASCENDING), ("provider_event_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"provider_event_id": {"$type": "string"}},
            name="payment_webhook_events_provider_event_unique",
        ),
    ],
    DatabaseCollections.PAYMENT_AUDIT_EVENTS: [
        IndexModel([("payment_id", ASCENDING)], name="payment_audit_events_payment_id_idx"),
        IndexModel([("order_id", ASCENDING)], name="payment_audit_events_order_id_idx"),
        IndexModel([("refund_id", ASCENDING)], name="payment_audit_events_refund_id_idx"),
        IndexModel([("webhook_event_id", ASCENDING)], name="payment_audit_events_webhook_event_id_idx"),
        IndexModel([("action", ASCENDING)], name="payment_audit_events_action_idx"),
        IndexModel([("actor_type", ASCENDING)], name="payment_audit_events_actor_type_idx"),
        IndexModel([("created_at", ASCENDING)], name="payment_audit_events_created_at_idx"),
    ],
    DatabaseCollections.REFUNDS: [
        IndexModel([("payment_id", ASCENDING)], name="refunds_payment_id_idx"),
        IndexModel([("order_id", ASCENDING)], name="refunds_order_id_idx"),
        IndexModel([("user_id", ASCENDING)], name="refunds_user_id_idx"),
        IndexModel([("status", ASCENDING)], name="refunds_status_idx"),
        IndexModel([("created_at", ASCENDING)], name="refunds_created_at_idx"),
        IndexModel(
            [("provider", ASCENDING), ("provider_refund_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"provider_refund_id": {"$type": "string"}},
            name="refunds_provider_refund_id_unique",
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
