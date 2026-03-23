"""Integration tests for ticket purchasing and cancellation flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

from app.db.collections import DatabaseCollections

from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
async def test_authenticated_user_can_purchase_ticket_and_available_seats_decrease(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticket Purchase Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=12, duration_minutes=160, price=260)

    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 1,
            "seat_number": 2,
        },
    )

    assert response.status_code == 201
    ticket = response.json()["data"]
    assert ticket["status"] == "purchased"
    assert ticket["seat_row"] == 1
    assert ticket["seat_number"] == 2

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1


@pytest.mark.asyncio
async def test_duplicate_seat_purchase_is_rejected(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_authenticated_user,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Duplicate Seat Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=13, duration_minutes=160, price=240)

    first_purchase = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 3,
            "seat_number": 4,
        },
    )
    assert first_purchase.status_code == 201

    second_user = await create_authenticated_user(email="second-user@example.com", name="Second User")
    second_purchase = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=second_user["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 3,
            "seat_number": 4,
        },
    )

    assert second_purchase.status_code == 409
    body = second_purchase.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Selected seat has already been purchased."


@pytest.mark.asyncio
async def test_purchase_outside_hall_bounds_is_rejected(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Hall Bounds Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=15, duration_minutes=160)

    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 99,
            "seat_number": 1,
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Seat coordinates are outside the configured hall dimensions."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_update", "time_shift", "expected_message"),
    [
        ("cancelled", None, "Only scheduled sessions can be purchased."),
        ("completed", None, "Only scheduled sessions can be purchased."),
        ("scheduled", timedelta(hours=-3), "Tickets can only be purchased for future sessions."),
    ],
)
async def test_purchase_for_cancelled_completed_or_past_sessions_is_rejected(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
    status_update: str,
    time_shift: timedelta | None,
    expected_message: str,
) -> None:
    movie = await create_movie(title=f"Unavailable Session {status_update}", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=16, duration_minutes=160)
    update_payload: dict[str, object] = {"status": status_update}
    if time_shift is not None:
        now = datetime.now(tz=timezone.utc)
        update_payload["start_time"] = now + time_shift
        update_payload["end_time"] = now + time_shift + timedelta(hours=2)
    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(session["id"])},
        {"$set": update_payload},
    )

    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 1,
            "seat_number": 1,
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == expected_message


@pytest.mark.asyncio
async def test_current_user_can_list_and_cancel_their_tickets_and_admin_can_list_all_tickets(
    client: httpx.AsyncClient,
    database,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticket Listing Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=17, duration_minutes=160, price=275)

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 5,
            "seat_number": 6,
        },
    )
    assert purchase_response.status_code == 201
    ticket = purchase_response.json()["data"]

    my_tickets_response = await client.get(f"{API_PREFIX}/tickets/me", headers=user_auth["headers"])
    assert my_tickets_response.status_code == 200
    my_tickets = my_tickets_response.json()["data"]
    assert len(my_tickets) == 1
    assert my_tickets[0]["movie_title"] == movie["title"]
    assert my_tickets[0]["is_cancellable"] is True

    admin_tickets_response = await client.get(f"{API_PREFIX}/admin/tickets", headers=admin_auth["headers"])
    assert admin_tickets_response.status_code == 200
    admin_ticket = admin_tickets_response.json()["data"][0]
    assert admin_ticket["user_email"] == "user@example.com"

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{ticket['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert cancel_response.status_code == 200
    cancelled_ticket = cancel_response.json()["data"]
    assert cancelled_ticket["status"] == "cancelled"
    assert cancelled_ticket["cancelled_at"] is not None

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]
    assert stored_ticket is not None
    assert stored_ticket["status"] == "cancelled"
