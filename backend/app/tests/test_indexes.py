"""Unit tests for MongoDB index bootstrap."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.core.constants import PaymentStatuses, TicketStatuses
from app.db.collections import DatabaseCollections
from app.db.indexes import COLLECTION_INDEXES, ensure_indexes


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
                    "ix_movies_title_uk": {"key": [("title.uk", 1)]},
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
            DatabaseCollections.ORDERS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "ix_orders_user_id": {"key": [("user_id", 1)]},
                    "ix_orders_session_id": {"key": [("session_id", 1)]},
                    "ix_orders_status": {"key": [("status", 1)]},
                }
            ),
            DatabaseCollections.TICKETS: FakeCollection(ticket_indexes),
            DatabaseCollections.PAYMENTS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "payments_order_id_idx": {"key": [("order_id", 1)]},
                    "payments_user_id_idx": {"key": [("user_id", 1)]},
                    "payments_status_idx": {"key": [("status", 1)]},
                    "payments_created_at_idx": {"key": [("created_at", 1)]},
                    "payments_idempotency_key_unique": {
                        "key": [("idempotency_key", 1)],
                        "unique": True,
                    },
                    "payments_provider_payment_id_unique": {
                        "key": [("provider", 1), ("provider_payment_id", 1)],
                        "unique": True,
                        "partialFilterExpression": {"provider_payment_id": {"$type": "string"}},
                    },
                    "payments_active_order_provider_unique": {
                        "key": [("order_id", 1), ("provider", 1)],
                        "unique": True,
                        "partialFilterExpression": {
                            "status": {
                                "$in": [
                                    PaymentStatuses.CREATED,
                                    PaymentStatuses.PENDING,
                                    PaymentStatuses.REQUIRES_ACTION,
                                    PaymentStatuses.SUCCEEDED,
                                ]
                            }
                        },
                    },
                }
            ),
            DatabaseCollections.PAYMENT_ATTEMPTS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "payment_attempts_payment_id_idx": {"key": [("payment_id", 1)]},
                    "payment_attempts_order_id_idx": {"key": [("order_id", 1)]},
                    "payment_attempts_status_idx": {"key": [("status", 1)]},
                    "payment_attempts_provider_attempt_id_unique": {
                        "key": [("provider", 1), ("provider_attempt_id", 1)],
                        "unique": True,
                        "partialFilterExpression": {"provider_attempt_id": {"$type": "string"}},
                    },
                }
            ),
            DatabaseCollections.PAYMENT_WEBHOOK_EVENTS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "payment_webhook_events_provider_idx": {"key": [("provider", 1)]},
                    "payment_webhook_events_payment_id_idx": {"key": [("payment_id", 1)]},
                    "payment_webhook_events_order_id_idx": {"key": [("order_id", 1)]},
                    "payment_webhook_events_refund_id_idx": {"key": [("refund_id", 1)]},
                    "payment_webhook_events_processing_status_idx": {"key": [("processing_status", 1)]},
                    "payment_webhook_events_created_at_idx": {"key": [("created_at", 1)]},
                    "payment_webhook_events_provider_event_unique": {
                        "key": [("provider", 1), ("provider_event_id", 1)],
                        "unique": True,
                        "partialFilterExpression": {"provider_event_id": {"$type": "string"}},
                    },
                }
            ),
            DatabaseCollections.PAYMENT_AUDIT_EVENTS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "payment_audit_events_payment_id_idx": {"key": [("payment_id", 1)]},
                    "payment_audit_events_order_id_idx": {"key": [("order_id", 1)]},
                    "payment_audit_events_refund_id_idx": {"key": [("refund_id", 1)]},
                    "payment_audit_events_webhook_event_id_idx": {"key": [("webhook_event_id", 1)]},
                    "payment_audit_events_action_idx": {"key": [("action", 1)]},
                    "payment_audit_events_actor_type_idx": {"key": [("actor_type", 1)]},
                    "payment_audit_events_created_at_idx": {"key": [("created_at", 1)]},
                }
            ),
            DatabaseCollections.REFUNDS: FakeCollection(
                {
                    "_id_": {"key": [("_id", 1)]},
                    "refunds_payment_id_idx": {"key": [("payment_id", 1)]},
                    "refunds_order_id_idx": {"key": [("order_id", 1)]},
                    "refunds_user_id_idx": {"key": [("user_id", 1)]},
                    "refunds_status_idx": {"key": [("status", 1)]},
                    "refunds_created_at_idx": {"key": [("created_at", 1)]},
                    "refunds_provider_refund_id_unique": {
                        "key": [("provider", 1), ("provider_refund_id", 1)],
                        "unique": True,
                        "partialFilterExpression": {"provider_refund_id": {"$type": "string"}},
                    },
                }
            ),
        }
    )


@pytest.mark.asyncio
async def test_ensure_indexes_accepts_equivalent_legacy_index_names() -> None:
    database = _build_database(
        {
            "_id_": {"key": [("_id", 1)]},
            "ix_tickets_user_id": {"key": [("user_id", 1)]},
            "ix_tickets_order_id": {"key": [("order_id", 1)]},
            "ix_tickets_session_id": {"key": [("session_id", 1)]},
            "tickets_status_idx": {"key": [("status", 1)]},
            "tickets_expires_at_idx": {"key": [("expires_at", 1)]},
            "tickets_active_session_seat_unique": {
                "key": [("session_id", 1), ("seat_row", 1), ("seat_number", 1)],
                "unique": True,
                "partialFilterExpression": {
                    "status": {"$in": [TicketStatuses.RESERVED, TicketStatuses.PURCHASED]}
                },
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
            "ix_tickets_order_id": {"key": [("order_id", 1)]},
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
    assert tickets_collection.created_batches == [[
        "tickets_status_idx",
        "tickets_expires_at_idx",
        "tickets_active_session_seat_unique",
    ]]


@pytest.mark.asyncio
async def test_ensure_indexes_replaces_purchase_only_ticket_seat_unique_index() -> None:
    database = _build_database(
        {
            "_id_": {"key": [("_id", 1)]},
            "ix_tickets_user_id": {"key": [("user_id", 1)]},
            "ix_tickets_order_id": {"key": [("order_id", 1)]},
            "ix_tickets_session_id": {"key": [("session_id", 1)]},
            "tickets_status_idx": {"key": [("status", 1)]},
            "tickets_expires_at_idx": {"key": [("expires_at", 1)]},
            "tickets_active_session_seat_unique": {
                "key": [("session_id", 1), ("seat_row", 1), ("seat_number", 1)],
                "unique": True,
                "partialFilterExpression": {"status": TicketStatuses.PURCHASED},
            },
        }
    )

    await ensure_indexes(database)

    tickets_collection = database[DatabaseCollections.TICKETS]
    assert tickets_collection.dropped_indexes == ["tickets_active_session_seat_unique"]
    assert tickets_collection.created_batches == [["tickets_active_session_seat_unique"]]


def test_payment_domain_indexes_are_configured() -> None:
    configured_names = {
        collection_name: {index.document["name"] for index in indexes}
        for collection_name, indexes in COLLECTION_INDEXES.items()
    }

    assert configured_names[DatabaseCollections.TICKETS] == {
        "tickets_user_id_idx",
        "tickets_order_id_idx",
        "tickets_session_id_idx",
        "tickets_status_idx",
        "tickets_expires_at_idx",
        "tickets_active_session_seat_unique",
    }
    assert configured_names[DatabaseCollections.PAYMENTS] == {
        "payments_order_id_idx",
        "payments_user_id_idx",
        "payments_status_idx",
        "payments_created_at_idx",
        "payments_idempotency_key_unique",
        "payments_provider_payment_id_unique",
        "payments_active_order_provider_unique",
    }
    assert configured_names[DatabaseCollections.PAYMENT_ATTEMPTS] == {
        "payment_attempts_payment_id_idx",
        "payment_attempts_order_id_idx",
        "payment_attempts_status_idx",
        "payment_attempts_provider_attempt_id_unique",
    }
    assert configured_names[DatabaseCollections.PAYMENT_WEBHOOK_EVENTS] == {
        "payment_webhook_events_provider_idx",
        "payment_webhook_events_payment_id_idx",
        "payment_webhook_events_order_id_idx",
        "payment_webhook_events_refund_id_idx",
        "payment_webhook_events_processing_status_idx",
        "payment_webhook_events_created_at_idx",
        "payment_webhook_events_provider_event_unique",
    }
    assert configured_names[DatabaseCollections.PAYMENT_AUDIT_EVENTS] == {
        "payment_audit_events_payment_id_idx",
        "payment_audit_events_order_id_idx",
        "payment_audit_events_refund_id_idx",
        "payment_audit_events_webhook_event_id_idx",
        "payment_audit_events_action_idx",
        "payment_audit_events_actor_type_idx",
        "payment_audit_events_created_at_idx",
    }
    assert configured_names[DatabaseCollections.REFUNDS] == {
        "refunds_payment_id_idx",
        "refunds_order_id_idx",
        "refunds_user_id_idx",
        "refunds_status_idx",
        "refunds_created_at_idx",
        "refunds_provider_refund_id_unique",
    }
