"""Integration tests for payment lifecycle API flows."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json

from bson import ObjectId
import httpx
import pytest

from app.db.collections import DatabaseCollections

from .conftest import API_PREFIX


def sign_fake_webhook_payload(payload: dict[str, object]) -> tuple[bytes, str]:
    """Build the exact raw body and fake-provider HMAC signature for webhook tests."""
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(b"fake-webhook-secret", raw_body, hashlib.sha256).hexdigest()
    return raw_body, signature


@pytest.mark.asyncio
async def test_order_payment_success_webhook_finalizes_once_and_records_history(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Payment Integration Movie")
    session = await create_session(movie_id=movie["id"], price=200)
    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 1, "seat_number": 1},
                {"seat_row": 1, "seat_number": 2},
            ],
        },
    )
    assert purchase_response.status_code == 201, purchase_response.text
    order = purchase_response.json()["data"]
    assert order["status"] == "pending_payment"
    assert {ticket["status"] for ticket in order["tickets"]} == {"reserved"}

    initiation_response = await client.post(
        f"{API_PREFIX}/orders/{order['id']}/payments",
        headers={**user_auth["headers"], "Idempotency-Key": "idem-integration-payment-1"},
        json={"metadata": {"source": "integration_test"}},
    )
    assert initiation_response.status_code == 201, initiation_response.text
    initiation = initiation_response.json()["data"]
    assert initiation["status"] == "pending"
    assert initiation["amount_minor"] == 40000

    reused_response = await client.post(
        f"{API_PREFIX}/orders/{order['id']}/payments",
        headers={**user_auth["headers"], "Idempotency-Key": "idem-integration-payment-2"},
        json={},
    )
    assert reused_response.status_code == 201, reused_response.text
    reused = reused_response.json()["data"]
    assert reused["payment_id"] == initiation["payment_id"]
    assert reused["reused"] is True

    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": "evt-integration-paid-1",
            "event_type": "payment.updated",
            "occurred_at": datetime.now(tz=timezone.utc).isoformat(),
            "payment": {
                "id": initiation["provider_payment_id"],
                "status": "paid",
                "amount_minor": initiation["amount_minor"],
                "currency": initiation["currency"],
            },
        }
    )
    webhook_response = await client.post(
        f"{API_PREFIX}/payments/webhook",
        headers={"x-fake-payment-signature": signature},
        content=raw_body,
    )
    assert webhook_response.status_code == 200, webhook_response.text
    processed = webhook_response.json()["data"]
    assert processed["processing_status"] == "processed"
    assert processed["payment_id"] == initiation["payment_id"]

    duplicate_response = await client.post(
        f"{API_PREFIX}/payments/webhook",
        headers={"x-fake-payment-signature": signature},
        content=raw_body,
    )
    assert duplicate_response.status_code == 200, duplicate_response.text
    duplicate = duplicate_response.json()["data"]
    assert duplicate["duplicate"] is True
    assert duplicate["processing_status"] == "processed"

    stored_order = await database[DatabaseCollections.ORDERS].find_one({"_id": ObjectId(order["id"])})
    stored_payment = await database[DatabaseCollections.PAYMENTS].find_one({"_id": ObjectId(initiation["payment_id"])})
    stored_tickets = await database[DatabaseCollections.TICKETS].find({"order_id": order["id"]}).to_list(length=10)
    stored_webhooks = await database[DatabaseCollections.PAYMENT_WEBHOOK_EVENTS].find(
        {"provider_event_id": "evt-integration-paid-1"}
    ).to_list(length=10)
    audit_events = await database[DatabaseCollections.PAYMENT_AUDIT_EVENTS].find(
        {"payment_id": initiation["payment_id"]}
    ).to_list(length=20)

    assert stored_order["status"] == "completed"
    assert stored_payment["status"] == "succeeded"
    assert {ticket["status"] for ticket in stored_tickets} == {"purchased"}
    assert len(stored_webhooks) == 1
    assert stored_webhooks[0]["processing_status"] == "processed"
    assert any(event["action"] == "payment.initiated" for event in audit_events)
    assert any(event["action"] == "webhook.processed" for event in audit_events)
