"""Integration tests for customer order details, PDF, and QR validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

from app.db.collections import DatabaseCollections
from app.security.order_validation import create_order_validation_token
from app.tests.integration.conftest import API_PREFIX


async def _purchase_order(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    session_id: str,
    seats: list[dict[str, int]],
) -> dict[str, object]:
    response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=headers,
        json={
            "session_id": session_id,
            "seats": seats,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_user_can_open_own_order_detail_with_validation_shape(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Detailed Order Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=12, duration_minutes=150, price=210)
    purchased_order = await _purchase_order(
        client,
        user_auth["headers"],
        session["id"],
        [{"seat_row": 1, "seat_number": 1}, {"seat_row": 1, "seat_number": 2}],
    )

    response = await client.get(
        f"{API_PREFIX}/users/me/orders/{purchased_order['id']}",
        headers=user_auth["headers"],
    )

    assert response.status_code == 200, response.text
    order = response.json()["data"]
    assert order["id"] == purchased_order["id"]
    assert order["movie_title"] == movie["title"]
    assert order["session_price"] == 210
    assert order["valid_for_entry"] is True
    assert order["entry_status_code"] == "valid"
    assert order["validation_token"]
    assert order["validation_url"].endswith(order["validation_token"])
    assert order["active_tickets_count"] == 2
    assert order["cancelled_tickets_count"] == 0
    assert order["checked_in_tickets_count"] == 0
    assert order["unchecked_active_tickets_count"] == 2
    assert len(order["tickets"]) == 2
    assert all(ticket["valid_for_entry"] is True for ticket in order["tickets"])
    assert all(ticket["checked_in_at"] is None for ticket in order["tickets"])


@pytest.mark.asyncio
async def test_user_cannot_open_or_download_another_users_order_detail(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_authenticated_user,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Private Order Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=13, duration_minutes=150, price=220)
    owner = await create_authenticated_user(email="order-detail-owner@example.com", name="Order Detail Owner")
    order = await _purchase_order(
        client,
        owner["headers"],
        session["id"],
        [{"seat_row": 2, "seat_number": 3}],
    )

    detail_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=user_auth["headers"],
    )
    pdf_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}/pdf",
        headers=user_auth["headers"],
    )

    assert detail_response.status_code == 403
    assert detail_response.json()["error"]["message"] == "You can only access your own orders."
    assert pdf_response.status_code == 403
    assert pdf_response.json()["error"]["message"] == "You can only access your own orders."


@pytest.mark.asyncio
async def test_order_pdf_download_returns_readable_pdf(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="PDF Order Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=14, duration_minutes=150, price=230)
    order = await _purchase_order(
        client,
        user_auth["headers"],
        session["id"],
        [{"seat_row": 3, "seat_number": 4}, {"seat_row": 3, "seat_number": 5}],
    )

    response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}/pdf",
        headers=user_auth["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


@pytest.mark.asyncio
async def test_admin_qr_validation_distinguishes_valid_cancelled_expired_invalid_and_missing_orders(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="QR Validation Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=15, duration_minutes=150, price=240)
    order = await _purchase_order(
        client,
        user_auth["headers"],
        session["id"],
        [{"seat_row": 4, "seat_number": 6}],
    )

    detail_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=user_auth["headers"],
    )
    assert detail_response.status_code == 200
    token = detail_response.json()["data"]["validation_token"]

    valid_response = await client.get(
        f"{API_PREFIX}/admin/orders/validate/{token}",
        headers=admin_auth["headers"],
    )
    assert valid_response.status_code == 200, valid_response.text
    valid_result = valid_response.json()["data"]
    assert valid_result["token_status"] == "valid_token"
    assert valid_result["is_valid_for_entry"] is True
    assert valid_result["validity_code"] == "valid"
    assert valid_result["can_check_in"] is True
    assert valid_result["active_tickets_count"] == 1
    assert valid_result["unchecked_active_tickets_count"] == 1
    assert valid_result["tickets"][0]["valid_for_entry"] is True

    cancel_response = await client.patch(
        f"{API_PREFIX}/orders/{order['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert cancel_response.status_code == 200

    cancelled_response = await client.get(
        f"{API_PREFIX}/admin/orders/validate/{token}",
        headers=admin_auth["headers"],
    )
    assert cancelled_response.status_code == 200
    cancelled_result = cancelled_response.json()["data"]
    assert cancelled_result["token_status"] == "valid_token"
    assert cancelled_result["is_valid_for_entry"] is False
    assert cancelled_result["validity_code"] == "cancelled"
    assert cancelled_result["can_check_in"] is False
    assert cancelled_result["order_status"] == "cancelled"
    assert cancelled_result["active_tickets_count"] == 0
    assert cancelled_result["cancelled_tickets_count"] == 1
    assert cancelled_result["tickets"][0]["valid_for_entry"] is False

    expired_session = await create_session(movie_id=movie["id"], start_hour=16, duration_minutes=150, price=240)
    expired_order = await _purchase_order(
        client,
        user_auth["headers"],
        expired_session["id"],
        [{"seat_row": 4, "seat_number": 7}],
    )
    expired_detail_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{expired_order['id']}",
        headers=user_auth["headers"],
    )
    assert expired_detail_response.status_code == 200
    expired_token = expired_detail_response.json()["data"]["validation_token"]
    now = datetime.now(tz=timezone.utc)
    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(expired_session["id"])},
        {
            "$set": {
                "start_time": now - timedelta(hours=3),
                "end_time": now - timedelta(hours=1),
            }
        },
    )
    expired_response = await client.get(
        f"{API_PREFIX}/admin/orders/validate/{expired_token}",
        headers=admin_auth["headers"],
    )
    assert expired_response.status_code == 200
    expired_result = expired_response.json()["data"]
    assert expired_result["token_status"] == "valid_token"
    assert expired_result["is_valid_for_entry"] is False
    assert expired_result["validity_code"] == "expired"
    assert expired_result["can_check_in"] is False

    invalid_response = await client.get(
        f"{API_PREFIX}/admin/orders/validate/not-a-real-token",
        headers=admin_auth["headers"],
    )
    assert invalid_response.status_code == 200
    invalid_result = invalid_response.json()["data"]
    assert invalid_result["token_status"] == "invalid_token"
    assert invalid_result["validity_code"] == "invalid_token"
    assert invalid_result["is_valid_for_entry"] is False

    missing_order_token = create_order_validation_token(str(ObjectId()))
    missing_response = await client.get(
        f"{API_PREFIX}/admin/orders/validate/{missing_order_token}",
        headers=admin_auth["headers"],
    )
    assert missing_response.status_code == 200
    missing_result = missing_response.json()["data"]
    assert missing_result["token_status"] == "order_not_found"
    assert missing_result["validity_code"] == "order_not_found"
    assert missing_result["is_valid_for_entry"] is False


@pytest.mark.asyncio
async def test_admin_check_in_changes_qr_state_to_already_used_and_blocks_repeat(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Check In Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=17, duration_minutes=150, price=260)
    order = await _purchase_order(
        client,
        user_auth["headers"],
        session["id"],
        [{"seat_row": 6, "seat_number": 1}, {"seat_row": 6, "seat_number": 2}],
    )
    detail_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=user_auth["headers"],
    )
    assert detail_response.status_code == 200
    token = detail_response.json()["data"]["validation_token"]

    check_in_response = await client.post(
        f"{API_PREFIX}/admin/orders/{order['id']}/check-in",
        headers=admin_auth["headers"],
    )

    assert check_in_response.status_code == 200, check_in_response.text
    checked_in = check_in_response.json()["data"]
    assert checked_in["validity_code"] == "already_used"
    assert checked_in["is_valid_for_entry"] is False
    assert checked_in["can_check_in"] is False
    assert checked_in["checked_in_tickets_count"] == 2
    assert checked_in["unchecked_active_tickets_count"] == 0
    assert all(ticket["checked_in_at"] is not None for ticket in checked_in["tickets"])
    assert all(ticket["valid_for_entry"] is False for ticket in checked_in["tickets"])

    stored_tickets = await database[DatabaseCollections.TICKETS].find({"order_id": order["id"]}).to_list(length=10)
    assert len(stored_tickets) == 2
    assert all(ticket["checked_in_at"] is not None for ticket in stored_tickets)

    validation_response = await client.get(
        f"{API_PREFIX}/admin/orders/validate/{token}",
        headers=admin_auth["headers"],
    )
    assert validation_response.status_code == 200
    validation = validation_response.json()["data"]
    assert validation["validity_code"] == "already_used"
    assert validation["checked_in_tickets_count"] == 2

    repeated_response = await client.post(
        f"{API_PREFIX}/admin/orders/{order['id']}/check-in",
        headers=admin_auth["headers"],
    )
    assert repeated_response.status_code == 409
    assert repeated_response.json()["error"]["message"] == "Order has already been checked in."

    user_check_in_response = await client.post(
        f"{API_PREFIX}/admin/orders/{order['id']}/check-in",
        headers=user_auth["headers"],
    )
    assert user_check_in_response.status_code == 403

    user_cancel_response = await client.patch(
        f"{API_PREFIX}/orders/{order['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert user_cancel_response.status_code == 409
    assert user_cancel_response.json()["error"]["message"] == "Orders with checked-in tickets cannot be cancelled."


@pytest.mark.asyncio
async def test_cancelled_ticket_state_is_reflected_in_order_detail_validity(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Partial Detail Cancellation Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=16, duration_minutes=150, price=250)
    order = await _purchase_order(
        client,
        user_auth["headers"],
        session["id"],
        [{"seat_row": 5, "seat_number": 1}, {"seat_row": 5, "seat_number": 2}],
    )

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{order['tickets'][0]['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert cancel_response.status_code == 200

    detail_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=user_auth["headers"],
    )

    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["status"] == "partially_cancelled"
    assert detail["valid_for_entry"] is True
    assert detail["active_tickets_count"] == 1
    assert detail["cancelled_tickets_count"] == 1
    assert sorted(ticket["valid_for_entry"] for ticket in detail["tickets"]) == [False, True]
    assert {ticket["status"] for ticket in detail["tickets"]} == {"cancelled", "purchased"}
