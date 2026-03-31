"""Integration tests for order-based multi-ticket purchase flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

from app.core.exceptions import DatabaseException
from app.db.collections import DatabaseCollections
from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
async def test_user_can_purchase_multiple_tickets_in_one_order_and_update_session_counters(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Bulk Purchase Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=12, duration_minutes=150, price=210)

    response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 1, "seat_number": 1},
                {"seat_row": 1, "seat_number": 2},
                {"seat_row": 1, "seat_number": 3},
            ],
        },
    )

    assert response.status_code == 201, response.text
    order = response.json()["data"]
    assert order["status"] == "completed"
    assert order["tickets_count"] == 3
    assert order["active_tickets_count"] == 3
    assert order["cancelled_tickets_count"] == 0
    assert order["total_price"] == 630
    assert len(order["tickets"]) == 3
    assert {ticket["order_id"] for ticket in order["tickets"]} == {order["id"]}
    assert {(ticket["seat_row"], ticket["seat_number"]) for ticket in order["tickets"]} == {
        (1, 1),
        (1, 2),
        (1, 3),
    }

    stored_order = await database[DatabaseCollections.ORDERS].find_one({"_id": ObjectId(order["id"])})
    assert stored_order is not None
    assert stored_order["tickets_count"] == 3
    assert stored_order["total_price"] == 630

    stored_tickets = await database[DatabaseCollections.TICKETS].find({"order_id": order["id"]}).to_list(length=10)
    assert len(stored_tickets) == 3
    assert {ticket["order_id"] for ticket in stored_tickets} == {order["id"]}

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 3

    orders_response = await client.get(f"{API_PREFIX}/users/me/orders", headers=user_auth["headers"])
    assert orders_response.status_code == 200
    orders = orders_response.json()["data"]
    assert len(orders) == 1
    assert orders[0]["id"] == order["id"]
    assert orders[0]["movie_title"] == movie["title"]

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_payload = seats_response.json()["data"]
    assert seats_payload["available_seats"] == seats_payload["total_seats"] - 3
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 1 and seat["number"] == 1
    )["is_available"] is False
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 1 and seat["number"] == 4
    )["is_available"] is True


@pytest.mark.asyncio
async def test_order_purchase_rejects_duplicate_seats_in_payload(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Duplicate Seat Payload", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=13, duration_minutes=150, price=200)

    response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 2, "seat_number": 4},
                {"seat_row": 2, "seat_number": 4},
            ],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "request_validation_error"


@pytest.mark.asyncio
async def test_order_purchase_rejects_occupied_seat_and_keeps_counter_unchanged(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_authenticated_user,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Occupied Seat Order", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=14, duration_minutes=150, price=220)

    first_purchase = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [{"seat_row": 3, "seat_number": 3}],
        },
    )
    assert first_purchase.status_code == 201

    second_user = await create_authenticated_user(email="bulk-second@example.com", name="Bulk Second")
    second_purchase = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=second_user["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 3, "seat_number": 3},
                {"seat_row": 3, "seat_number": 4},
            ],
        },
    )

    assert second_purchase.status_code == 409
    body = second_purchase.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "One or more selected seats have already been purchased."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1


@pytest.mark.asyncio
async def test_order_purchase_rejects_seat_outside_hall_bounds(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Outside Bounds Order", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=15, duration_minutes=150, price=190)

    response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [{"seat_row": 99, "seat_number": 1}],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == "Seat coordinates are outside the configured hall dimensions."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_update", "start_shift", "end_shift", "expected_message"),
    [
        ("cancelled", timedelta(days=1), timedelta(days=1, hours=2), "Cancelled sessions cannot be purchased."),
        ("scheduled", timedelta(hours=-3), timedelta(hours=-1), "Completed sessions cannot be purchased."),
        ("scheduled", timedelta(minutes=-20), timedelta(hours=2), "Past sessions cannot be purchased."),
    ],
)
async def test_order_purchase_rejects_invalid_or_unavailable_sessions(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
    status_update: str,
    start_shift: timedelta,
    end_shift: timedelta,
    expected_message: str,
) -> None:
    movie = await create_movie(title="Unavailable Order Session", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=16, duration_minutes=150, price=205)
    now = datetime.now(tz=timezone.utc)

    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(session["id"])},
        {
            "$set": {
                "status": status_update,
                "start_time": now + start_shift,
                "end_time": now + end_shift,
            }
        },
    )

    response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [{"seat_row": 1, "seat_number": 1}],
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == expected_message


@pytest.mark.asyncio
async def test_order_purchase_rejects_when_requested_seats_exceed_available_and_counter_stays_valid(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Short On Seats", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=17, duration_minutes=150, price=230)

    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(session["id"])},
        {"$set": {"available_seats": 1}},
    )

    response = await client.post(
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

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "There are not enough available seats left for this session."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == 1


@pytest.mark.asyncio
async def test_multi_ticket_order_purchase_rolls_back_transaction_on_ticket_insert_failure(
    client: httpx.AsyncClient,
    database,
    monkeypatch: pytest.MonkeyPatch,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Transactional Order Failure", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=18, duration_minutes=150, price=240)
    original_create_ticket = None

    from app.repositories.tickets import TicketRepository

    original_create_ticket = TicketRepository.create_ticket
    create_attempts = 0

    async def fail_on_second_ticket(
        self,
        document: dict[str, object],
        *,
        db_session=None,
    ) -> dict[str, object]:
        nonlocal create_attempts
        create_attempts += 1
        if create_attempts == 2:
            raise DatabaseException("Simulated second ticket insert failure.")
        return await original_create_ticket(self, document, db_session=db_session)

    monkeypatch.setattr(
        "app.repositories.tickets.TicketRepository.create_ticket",
        fail_on_second_ticket,
    )

    response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 2, "seat_number": 1},
                {"seat_row": 2, "seat_number": 2},
            ],
        },
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "database_error"
    assert body["error"]["message"] == "Simulated second ticket insert failure."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_orders = await database[DatabaseCollections.ORDERS].count_documents({"session_id": session["id"]})
    stored_tickets = await database[DatabaseCollections.TICKETS].count_documents({"session_id": session["id"]})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]
    assert stored_orders == 0
    assert stored_tickets == 0


@pytest.mark.asyncio
async def test_single_ticket_wrapper_creates_order_and_returns_ticket_with_order_id(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Legacy Wrapper Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=18, duration_minutes=150, price=240)

    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 4,
            "seat_number": 5,
        },
    )

    assert response.status_code == 201
    ticket = response.json()["data"]
    assert ticket["order_id"] is not None

    stored_order = await database[DatabaseCollections.ORDERS].find_one({"_id": ObjectId(ticket["order_id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket["id"])})
    assert stored_order is not None
    assert stored_order["tickets_count"] == 1
    assert stored_ticket is not None
    assert stored_ticket["order_id"] == ticket["order_id"]


@pytest.mark.asyncio
async def test_cancelling_one_ticket_from_multi_ticket_order_updates_order_status_and_releases_one_seat(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Partial Cancellation Order", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=19, duration_minutes=150, price=250)

    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 5, "seat_number": 1},
                {"seat_row": 5, "seat_number": 2},
            ],
        },
    )
    assert purchase_response.status_code == 201
    order = purchase_response.json()["data"]

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{order['tickets'][0]['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"

    refreshed_order_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=user_auth["headers"],
    )
    assert refreshed_order_response.status_code == 200
    refreshed_order = refreshed_order_response.json()["data"]
    assert refreshed_order["status"] == "partially_cancelled"
    assert refreshed_order["active_tickets_count"] == 1
    assert refreshed_order["cancelled_tickets_count"] == 1

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_payload = seats_response.json()["data"]
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 5 and seat["number"] == 1
    )["is_available"] is True
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 5 and seat["number"] == 2
    )["is_available"] is False


@pytest.mark.asyncio
async def test_full_cancellation_marks_order_cancelled_and_repeated_ticket_cancellation_is_rejected(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Full Cancellation Order", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=20, duration_minutes=150, price=260)

    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 6, "seat_number": 1},
                {"seat_row": 6, "seat_number": 2},
            ],
        },
    )
    assert purchase_response.status_code == 201
    order = purchase_response.json()["data"]

    for ticket in order["tickets"]:
        cancel_response = await client.patch(
            f"{API_PREFIX}/tickets/{ticket['id']}/cancel",
            headers=user_auth["headers"],
        )
        assert cancel_response.status_code == 200

    repeated_cancel = await client.patch(
        f"{API_PREFIX}/tickets/{order['tickets'][0]['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert repeated_cancel.status_code == 409
    assert repeated_cancel.json()["error"]["message"] == "Ticket has already been cancelled."

    refreshed_order_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=user_auth["headers"],
    )
    assert refreshed_order_response.status_code == 200
    refreshed_order = refreshed_order_response.json()["data"]
    assert refreshed_order["status"] == "cancelled"
    assert refreshed_order["active_tickets_count"] == 0
    assert refreshed_order["cancelled_tickets_count"] == 2

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_payload = seats_response.json()["data"]
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 6 and seat["number"] == 1
    )["is_available"] is True
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 6 and seat["number"] == 2
    )["is_available"] is True
