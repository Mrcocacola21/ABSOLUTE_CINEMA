"""Integration tests for ticket purchase and cancellation flows."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId
from pymongo.errors import OperationFailure

from app.core.exceptions import DatabaseException
from app.db.collections import DatabaseCollections

from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
async def test_authenticated_user_can_purchase_ticket_and_session_seat_map_updates(
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

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_payload = seats_response.json()["data"]
    occupied_seat = next(
        seat for seat in seats_payload["seats"] if seat["row"] == 1 and seat["number"] == 2
    )
    free_seat = next(
        seat for seat in seats_payload["seats"] if seat["row"] == 1 and seat["number"] == 1
    )
    assert seats_payload["available_seats"] == seats_payload["total_seats"] - 1
    assert occupied_seat["is_available"] is False
    assert free_seat["is_available"] is True


@pytest.mark.asyncio
async def test_duplicate_seat_purchase_is_rejected_without_double_decrement(
    client: httpx.AsyncClient,
    database,
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

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1

    stored_tickets = await database[DatabaseCollections.TICKETS].count_documents({"session_id": session["id"]})
    assert stored_tickets == 1


@pytest.mark.asyncio
async def test_fast_concurrent_requests_for_same_seat_only_create_one_ticket(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_authenticated_user,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Concurrent Seat Purchase Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=14, duration_minutes=160, price=255)

    second_user = await create_authenticated_user(email="seat-race-2@example.com", name="Seat Race 2")
    third_user = await create_authenticated_user(email="seat-race-3@example.com", name="Seat Race 3")

    async def purchase(headers: dict[str, str]) -> httpx.Response:
        return await client.post(
            f"{API_PREFIX}/tickets/purchase",
            headers=headers,
            json={
                "session_id": session["id"],
                "seat_row": 6,
                "seat_number": 8,
            },
        )

    responses = await asyncio.gather(
        purchase(user_auth["headers"]),
        purchase(second_user["headers"]),
        purchase(third_user["headers"]),
    )

    assert sorted(response.status_code for response in responses) == [201, 409, 409]
    conflict_messages = [
        response.json()["error"]["message"]
        for response in responses
        if response.status_code == 409
    ]
    assert conflict_messages == [
        "Selected seat has already been purchased.",
        "Selected seat has already been purchased.",
    ]

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_tickets = await database[DatabaseCollections.TICKETS].count_documents(
        {
            "session_id": session["id"],
            "seat_row": 6,
            "seat_number": 8,
            "status": "purchased",
        }
    )
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1
    assert stored_tickets == 1


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
    assert body["error"]["message"] == "Seat is outside the configured hall dimensions: row 99, seat 1."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_update", "start_shift", "end_shift", "expected_message"),
    [
        ("cancelled", timedelta(days=1), timedelta(days=1, hours=2), "Cancelled sessions cannot be purchased."),
        ("scheduled", timedelta(hours=-3), timedelta(hours=-1), "Completed sessions cannot be purchased."),
        ("scheduled", timedelta(minutes=-15), timedelta(hours=2), "Past sessions cannot be purchased."),
    ],
)
async def test_purchase_for_unavailable_sessions_is_rejected(
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
    movie = await create_movie(title=f"Unavailable Session {status_update}", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=16, duration_minutes=160)
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
async def test_purchase_is_rejected_when_no_seats_left_and_counter_stays_non_negative(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Sold Out Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=17, duration_minutes=160)
    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(session["id"])},
        {"$set": {"available_seats": 0}},
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
    assert body["error"]["message"] == "There are no available seats left for this session."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == 0


@pytest.mark.asyncio
async def test_single_ticket_purchase_wrapper_rolls_back_transaction_on_ticket_insert_failure(
    client: httpx.AsyncClient,
    database,
    monkeypatch: pytest.MonkeyPatch,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticket Insert Failure Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=17, duration_minutes=160)

    async def fail_create_ticket(
        self,
        document: dict[str, object],
        *,
        db_session=None,
    ) -> dict[str, object]:
        _ = (self, document, db_session)
        raise DatabaseException("Simulated ticket insert failure.")

    monkeypatch.setattr(
        "app.repositories.tickets.TicketRepository.create_ticket",
        fail_create_ticket,
    )

    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 1,
            "seat_number": 3,
        },
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "database_error"
    assert body["error"]["message"] == "Simulated ticket insert failure."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_orders = await database[DatabaseCollections.ORDERS].count_documents({"session_id": session["id"]})
    stored_tickets = await database[DatabaseCollections.TICKETS].count_documents({"session_id": session["id"]})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]
    assert stored_orders == 0
    assert stored_tickets == 0


@pytest.mark.asyncio
async def test_current_user_can_list_and_cancel_tickets_and_admin_can_list_all_tickets(
    client: httpx.AsyncClient,
    database,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_authenticated_user,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticket Listing Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=18, duration_minutes=160, price=275)

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

    second_user = await create_authenticated_user(email="other-ticket-list@example.com", name="Other Ticket List")
    second_purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=second_user["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 5,
            "seat_number": 7,
        },
    )
    assert second_purchase_response.status_code == 201
    second_ticket = second_purchase_response.json()["data"]

    my_tickets_response = await client.get(f"{API_PREFIX}/tickets/me", headers=user_auth["headers"])
    assert my_tickets_response.status_code == 200
    my_tickets = my_tickets_response.json()["data"]
    assert len(my_tickets) == 1
    assert my_tickets[0]["id"] == ticket["id"]
    assert my_tickets[0]["id"] != second_ticket["id"]
    assert my_tickets[0]["movie_title"] == movie["title"]
    assert my_tickets[0]["is_cancellable"] is True
    assert my_tickets[0]["user_email"] is None

    admin_tickets_response = await client.get(f"{API_PREFIX}/admin/tickets", headers=admin_auth["headers"])
    assert admin_tickets_response.status_code == 200
    admin_tickets = admin_tickets_response.json()["data"]
    assert {admin_ticket["id"] for admin_ticket in admin_tickets} == {ticket["id"], second_ticket["id"]}
    assert {admin_ticket["user_email"] for admin_ticket in admin_tickets} == {
        "user@example.com",
        "other-ticket-list@example.com",
    }

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
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1
    assert stored_ticket is not None
    assert stored_ticket["status"] == "cancelled"

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_payload = seats_response.json()["data"]
    released_seat = next(
        seat for seat in seats_payload["seats"] if seat["row"] == 5 and seat["number"] == 6
    )
    assert released_seat["is_available"] is True
    assert seats_payload["available_seats"] == seats_payload["total_seats"] - 1


@pytest.mark.asyncio
async def test_ticket_purchase_rejects_attempt_to_override_authenticated_user(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticket User Override Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=18, duration_minutes=160)

    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 1,
            "seat_number": 4,
            "user_id": str(ObjectId()),
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "request_validation_error"
    assert body["error"]["message"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_user_cannot_cancel_another_users_ticket_but_admin_can(
    client: httpx.AsyncClient,
    database,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_authenticated_user,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticket Ownership Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=19, duration_minutes=160)
    ticket_owner = await create_authenticated_user(email="ticket-owner@example.com", name="Ticket Owner")

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=ticket_owner["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 6,
            "seat_number": 2,
        },
    )
    assert purchase_response.status_code == 201
    ticket_id = purchase_response.json()["data"]["id"]

    forbidden_cancel = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )
    assert forbidden_cancel.status_code == 403
    assert forbidden_cancel.json()["error"]["message"] == "You can only cancel your own tickets."

    admin_cancel = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=admin_auth["headers"],
    )
    assert admin_cancel.status_code == 200, admin_cancel.text
    assert admin_cancel.json()["data"]["status"] == "cancelled"

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket_id)})
    assert stored_session is not None
    assert stored_ticket is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]
    assert stored_ticket["status"] == "cancelled"


@pytest.mark.asyncio
async def test_session_cancellation_cascade_marks_ticket_cancelled_and_rejects_repeated_ticket_cancel(
    client: httpx.AsyncClient,
    database,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Cancelled Session Ticket Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=19, duration_minutes=160)

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 7,
            "seat_number": 2,
        },
    )
    assert purchase_response.status_code == 201
    ticket_id = purchase_response.json()["data"]["id"]

    cancel_session_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert cancel_session_response.status_code == 200
    assert cancel_session_response.json()["data"]["status"] == "cancelled"

    my_tickets_response = await client.get(f"{API_PREFIX}/tickets/me", headers=user_auth["headers"])
    assert my_tickets_response.status_code == 200
    listed_ticket = my_tickets_response.json()["data"][0]
    assert listed_ticket["status"] == "cancelled"
    assert listed_ticket["is_cancellable"] is False

    cancel_ticket_response = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )
    assert cancel_ticket_response.status_code == 409
    assert cancel_ticket_response.json()["error"]["message"] == "Ticket has already been cancelled."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket_id)})
    assert stored_session is not None
    assert stored_ticket is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]
    assert stored_ticket["status"] == "cancelled"

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_payload = seats_response.json()["data"]
    released_seat = next(
        seat for seat in seats_payload["seats"] if seat["row"] == 7 and seat["number"] == 2
    )
    assert released_seat["is_available"] is True
    assert seats_payload["available_seats"] == seats_payload["total_seats"]


@pytest.mark.asyncio
async def test_ticket_cancellation_is_rejected_when_repeated_twice(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Repeated Ticket Cancellation", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=19, duration_minutes=160)

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 2,
            "seat_number": 2,
        },
    )
    assert purchase_response.status_code == 201
    ticket_id = purchase_response.json()["data"]["id"]

    first_cancel = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )
    assert first_cancel.status_code == 200

    second_cancel = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )
    assert second_cancel.status_code == 409
    body = second_cancel.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Ticket has already been cancelled."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start_shift", "end_shift", "expected_message"),
    [
        (timedelta(minutes=-20), timedelta(hours=2), "Tickets can only be cancelled before the session starts."),
        (timedelta(hours=-3), timedelta(hours=-1), "Tickets for completed sessions cannot be cancelled."),
    ],
)
async def test_ticket_cancellation_for_started_or_completed_sessions_is_rejected(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
    start_shift: timedelta,
    end_shift: timedelta,
    expected_message: str,
) -> None:
    movie = await create_movie(title="Unavailable Ticket Cancellation Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=20, duration_minutes=160)

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 8,
            "seat_number": 4,
        },
    )
    assert purchase_response.status_code == 201
    ticket_id = purchase_response.json()["data"]["id"]

    now = datetime.now(tz=timezone.utc)
    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(session["id"])},
        {
            "$set": {
                "status": "scheduled",
                "start_time": now + start_shift,
                "end_time": now + end_shift,
            }
        },
    )

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )

    assert cancel_response.status_code == 409
    body = cancel_response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == expected_message

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket_id)})
    assert stored_session is not None
    assert stored_ticket is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1
    assert stored_ticket["status"] == "purchased"


@pytest.mark.asyncio
async def test_ticket_cancellation_fails_without_partial_commit_when_session_counter_is_inconsistent(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Counter Reconciliation Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=20, duration_minutes=160)

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 4,
            "seat_number": 7,
        },
    )
    assert purchase_response.status_code == 201
    ticket_id = purchase_response.json()["data"]["id"]

    session_document = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    assert session_document is not None
    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(session["id"])},
        {"$set": {"available_seats": session_document["total_seats"]}},
    )

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )
    assert cancel_response.status_code == 503
    body = cancel_response.json()
    assert body["error"]["code"] == "database_error"
    assert body["error"]["message"] == "Ticket cancellation could not restore the session seat counter."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket_id)})
    assert stored_session is not None
    assert stored_ticket is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]
    assert stored_ticket["status"] == "purchased"


@pytest.mark.asyncio
async def test_ticket_cancellation_transaction_rolls_back_when_order_update_fails(
    client: httpx.AsyncClient,
    database,
    monkeypatch: pytest.MonkeyPatch,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticket Cancellation Rollback Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=20, duration_minutes=160)

    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 4, "seat_number": 4},
                {"seat_row": 4, "seat_number": 5},
            ],
        },
    )
    assert purchase_response.status_code == 201
    order = purchase_response.json()["data"]
    ticket_id = order["tickets"][0]["id"]

    async def fail_update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = (self, order_id, updates, updated_at, db_session)
        raise DatabaseException("Simulated order aggregate update failure.")

    monkeypatch.setattr(
        "app.repositories.orders.OrderRepository.update_order",
        fail_update_order,
    )

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )

    assert cancel_response.status_code == 503
    body = cancel_response.json()
    assert body["error"]["code"] == "database_error"
    assert body["error"]["message"] == "Simulated order aggregate update failure."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket_id)})
    stored_order = await database[DatabaseCollections.ORDERS].find_one({"_id": ObjectId(order["id"])})
    assert stored_session is not None
    assert stored_ticket is not None
    assert stored_order is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 2
    assert stored_ticket["status"] == "purchased"
    assert stored_order["status"] == "completed"


@pytest.mark.asyncio
async def test_ticket_cancellation_retries_transient_transaction_error_and_commits_cleanly(
    client: httpx.AsyncClient,
    database,
    monkeypatch: pytest.MonkeyPatch,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Transient Cancellation Retry", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=20, duration_minutes=160)

    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 5, "seat_number": 2},
                {"seat_row": 5, "seat_number": 3},
            ],
        },
    )
    assert purchase_response.status_code == 201
    order = purchase_response.json()["data"]
    ticket_id = order["tickets"][0]["id"]

    from app.repositories.orders import OrderRepository

    original_update_order = OrderRepository.update_order
    injected_failure = True

    async def fail_once_with_transient_error(
        self,
        order_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        nonlocal injected_failure
        if injected_failure:
            injected_failure = False
            exc = OperationFailure("Simulated transient cancellation error.")
            exc._add_error_label("TransientTransactionError")
            raise exc
        return await original_update_order(
            self,
            order_id,
            updates=updates,
            updated_at=updated_at,
            db_session=db_session,
        )

    monkeypatch.setattr(
        "app.repositories.orders.OrderRepository.update_order",
        fail_once_with_transient_error,
    )

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{ticket_id}/cancel",
        headers=user_auth["headers"],
    )

    assert cancel_response.status_code == 200, cancel_response.text
    cancelled_ticket = cancel_response.json()["data"]
    assert cancelled_ticket["status"] == "cancelled"

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_ticket = await database[DatabaseCollections.TICKETS].find_one({"_id": ObjectId(ticket_id)})
    stored_order = await database[DatabaseCollections.ORDERS].find_one({"_id": ObjectId(order["id"])})
    assert stored_session is not None
    assert stored_ticket is not None
    assert stored_order is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1
    assert stored_ticket["status"] == "cancelled"
    assert stored_order["status"] == "partially_cancelled"


@pytest.mark.asyncio
async def test_cancelled_ticket_seat_can_be_repurposed_and_counter_stays_bounded(
    client: httpx.AsyncClient,
    database,
    user_auth: dict[str, object],
    create_authenticated_user,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Repurchase Cancelled Seat", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=21, duration_minutes=160)

    first_purchase = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 6,
            "seat_number": 6,
        },
    )
    assert first_purchase.status_code == 201
    original_ticket_id = first_purchase.json()["data"]["id"]

    first_cancel = await client.patch(
        f"{API_PREFIX}/tickets/{original_ticket_id}/cancel",
        headers=user_auth["headers"],
    )
    assert first_cancel.status_code == 200

    second_user = await create_authenticated_user(email="repurchase-seat@example.com", name="Repurchase Seat")
    second_purchase = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=second_user["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 6,
            "seat_number": 6,
        },
    )
    assert second_purchase.status_code == 201, second_purchase.text

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_tickets = await database[DatabaseCollections.TICKETS].find(
        {
            "session_id": session["id"],
            "seat_row": 6,
            "seat_number": 6,
        }
    ).to_list(length=10)
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"] - 1
    assert len(stored_tickets) == 2
    assert sorted(ticket["status"] for ticket in stored_tickets) == ["cancelled", "purchased"]


@pytest.mark.asyncio
async def test_ticket_cancellation_returns_404_for_missing_ticket(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
) -> None:
    missing_ticket_id = str(ObjectId())

    response = await client.patch(
        f"{API_PREFIX}/tickets/{missing_ticket_id}/cancel",
        headers=user_auth["headers"],
    )

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Ticket was not found."
