"""Integration tests for admin session management flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

from app.core.exceptions import DatabaseException
from app.db.collections import DatabaseCollections

from app.tests.integration.conftest import API_PREFIX, build_session_window


@pytest.mark.asyncio
async def test_admin_can_create_list_and_read_session(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Session Creation Movie", duration_minutes=120)
    start_time, end_time = build_session_window(start_hour=10, duration_minutes=150)

    create_response = await client.post(
        f"{API_PREFIX}/admin/sessions",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "price": 250,
        },
    )

    assert create_response.status_code == 201
    session = create_response.json()["data"]
    session_id = session["id"]
    assert session["movie"]["id"] == movie["id"]
    assert session["available_seats"] == session["total_seats"]

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"movie_id": movie["id"]})
    assert stored_session is not None
    assert stored_session["available_seats"] == stored_session["total_seats"]

    list_response = await client.get(f"{API_PREFIX}/admin/sessions", headers=admin_auth["headers"])
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["data"]] == [session_id]

    read_response = await client.get(f"{API_PREFIX}/admin/sessions/{session_id}", headers=admin_auth["headers"])
    assert read_response.status_code == 200
    assert read_response.json()["data"]["movie"]["title"] == movie["title"]


@pytest.mark.asyncio
async def test_admin_can_read_attendance_session_details(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Attendance Detail Movie", duration_minutes=115)
    session = await create_session(movie_id=movie["id"], start_hour=17, duration_minutes=150, price=280)

    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 2, "seat_number": 5},
                {"seat_row": 2, "seat_number": 6},
            ],
        },
    )
    assert purchase_response.status_code == 201, purchase_response.text
    checked_order = purchase_response.json()["data"]

    unchecked_purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 2, "seat_number": 7},
            ],
        },
    )
    assert unchecked_purchase_response.status_code == 201, unchecked_purchase_response.text

    check_in_response = await client.post(
        f"{API_PREFIX}/admin/orders/{checked_order['id']}/check-in",
        headers=admin_auth["headers"],
    )
    assert check_in_response.status_code == 200, check_in_response.text

    cancelled_purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 2,
            "seat_number": 8,
        },
    )
    assert cancelled_purchase_response.status_code == 201, cancelled_purchase_response.text
    cancelled_ticket = cancelled_purchase_response.json()["data"]

    ticket_cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{cancelled_ticket['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert ticket_cancel_response.status_code == 200, ticket_cancel_response.text

    response = await client.get(
        f"{API_PREFIX}/admin/attendance/sessions/{session['id']}",
        headers=admin_auth["headers"],
    )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["session"]["id"] == session["id"]
    assert payload["session"]["movie"]["id"] == movie["id"]
    assert payload["tickets_sold"] == 3
    assert payload["checked_in_tickets_count"] == 2
    assert payload["unchecked_active_tickets_count"] == 1
    assert payload["cancelled_tickets_count"] == 1
    assert payload["attendance_rate"] == pytest.approx(3 / payload["session"]["total_seats"])
    assert payload["seat_map"]["session_id"] == session["id"]
    assert payload["seat_map"]["available_seats"] == payload["seat_map"]["total_seats"] - 3
    assert len(payload["occupied_tickets"]) == 3
    assert len(payload["cancelled_tickets"]) == 1
    assert payload["cancelled_tickets"][0]["id"] == cancelled_ticket["id"]
    assert payload["cancelled_tickets"][0]["seat_row"] == 2
    assert payload["cancelled_tickets"][0]["seat_number"] == 8
    assert payload["cancelled_tickets"][0]["cancelled_at"] is not None
    assert payload["occupied_tickets"][0]["seat_row"] == 2
    assert payload["occupied_tickets"][0]["seat_number"] == 5
    assert payload["occupied_tickets"][0]["user_name"] == user_auth["user"]["name"]
    assert payload["occupied_tickets"][0]["user_email"] == user_auth["user"]["email"]
    assert payload["occupied_tickets"][0]["order_status"] == "completed"
    tickets_by_seat = {
        (ticket["seat_row"], ticket["seat_number"]): ticket
        for ticket in payload["occupied_tickets"]
    }
    assert tickets_by_seat[(2, 5)]["checked_in_at"] is not None
    assert tickets_by_seat[(2, 6)]["checked_in_at"] is not None
    assert tickets_by_seat[(2, 7)]["checked_in_at"] is None
    assert next(
        seat for seat in payload["seat_map"]["seats"] if seat["row"] == 2 and seat["number"] == 5
    )["is_available"] is False
    assert next(
        seat for seat in payload["seat_map"]["seats"] if seat["row"] == 2 and seat["number"] == 8
    )["is_available"] is True


@pytest.mark.asyncio
async def test_admin_attendance_summary_counts_sold_used_cancelled_and_available_states(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Attendance Summary Movie", duration_minutes=115)
    session = await create_session(movie_id=movie["id"], start_hour=18, duration_minutes=150, price=260)

    order_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 3, "seat_number": 1},
                {"seat_row": 3, "seat_number": 2},
            ],
        },
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()["data"]

    check_in_response = await client.post(
        f"{API_PREFIX}/admin/orders/{order['id']}/check-in",
        headers=admin_auth["headers"],
    )
    assert check_in_response.status_code == 200, check_in_response.text

    cancelled_purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 3,
            "seat_number": 3,
        },
    )
    assert cancelled_purchase_response.status_code == 201, cancelled_purchase_response.text
    cancelled_ticket = cancelled_purchase_response.json()["data"]

    cancel_response = await client.patch(
        f"{API_PREFIX}/tickets/{cancelled_ticket['id']}/cancel",
        headers=user_auth["headers"],
    )
    assert cancel_response.status_code == 200, cancel_response.text

    response = await client.get(f"{API_PREFIX}/admin/attendance", headers=admin_auth["headers"])

    assert response.status_code == 200, response.text
    report = response.json()["data"]
    assert report["total_sessions"] == 1
    assert report["total_tickets_sold"] == 2
    assert report["total_checked_in_tickets"] == 2
    assert report["total_unchecked_active_tickets"] == 0
    assert report["total_cancelled_tickets"] == 1
    summary = report["sessions"][0]
    assert summary["session_id"] == session["id"]
    assert summary["tickets_sold"] == 2
    assert summary["checked_in_tickets_count"] == 2
    assert summary["unchecked_active_tickets_count"] == 0
    assert summary["cancelled_tickets_count"] == 1
    assert summary["available_seats"] == summary["total_seats"] - 2
    assert summary["attendance_rate"] == pytest.approx(2 / summary["total_seats"])


@pytest.mark.asyncio
async def test_attendance_session_details_returns_404_for_unknown_session(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
) -> None:
    response = await client.get(
        f"{API_PREFIX}/admin/attendance/sessions/{ObjectId()}",
        headers=admin_auth["headers"],
    )

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Session was not found."


@pytest.mark.asyncio
async def test_overlapping_session_creation_is_rejected(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Overlap Movie", duration_minutes=120)
    await create_session(movie_id=movie["id"], start_hour=10, duration_minutes=180)
    overlap_start, overlap_end = build_session_window(start_hour=11, duration_minutes=150)

    response = await client.post(
        f"{API_PREFIX}/admin/sessions",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": overlap_start.isoformat(),
            "end_time": overlap_end.isoformat(),
            "price": 220,
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Session overlaps with an existing session in the only hall."


@pytest.mark.asyncio
async def test_batch_session_creation_returns_created_and_rejected_dates(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
    database,
) -> None:
    movie = await create_movie(title="Batch Planning Movie", duration_minutes=120)
    await create_session(movie_id=movie["id"], day_offset=2, start_hour=15, duration_minutes=150)
    first_start, first_end = build_session_window(day_offset=1, start_hour=15, duration_minutes=150)
    conflict_start, _ = build_session_window(day_offset=2, start_hour=15, duration_minutes=150)
    third_start, _ = build_session_window(day_offset=4, start_hour=15, duration_minutes=150)

    response = await client.post(
        f"{API_PREFIX}/admin/sessions/batch",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": first_start.isoformat(),
            "end_time": first_end.isoformat(),
            "price": 240,
            "dates": [
                first_start.date().isoformat(),
                conflict_start.date().isoformat(),
                third_start.date().isoformat(),
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["requested_count"] == 3
    assert body["created_count"] == 2
    assert body["rejected_count"] == 1
    assert [session["start_time"][:10] for session in body["created_sessions"]] == [
        first_start.date().isoformat(),
        third_start.date().isoformat(),
    ]
    assert len(body["rejected_dates"]) == 1
    rejected = body["rejected_dates"][0]
    assert rejected["date"] == conflict_start.date().isoformat()
    assert rejected["code"] == "conflict"
    assert rejected["message"] == "Session overlaps with an existing session in the only hall."
    assert rejected["blocking_session_id"]

    count = await database[DatabaseCollections.SESSIONS].count_documents({"movie_id": movie["id"]})
    assert count == 3


@pytest.mark.asyncio
async def test_batch_session_creation_keeps_future_dates_when_one_requested_day_is_in_the_past(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Batch Past Date Movie", duration_minutes=110)
    future_start, future_end = build_session_window(day_offset=2, start_hour=17, duration_minutes=140)
    past_date = (future_start - timedelta(days=4)).date()

    response = await client.post(
        f"{API_PREFIX}/admin/sessions/batch",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": future_start.isoformat(),
            "end_time": future_end.isoformat(),
            "price": 225,
            "dates": [
                past_date.isoformat(),
                future_start.date().isoformat(),
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["created_count"] == 1
    assert body["rejected_count"] == 1
    assert body["rejected_dates"][0]["date"] == past_date.isoformat()
    assert body["rejected_dates"][0]["code"] == "validation_error"
    assert body["rejected_dates"][0]["message"] == "Session start time must be in the future."

    stored_sessions = await database[DatabaseCollections.SESSIONS].find({"movie_id": movie["id"]}).to_list(length=10)
    assert len(stored_sessions) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start_hour", "end_delta_minutes", "expected_code", "expected_message"),
    [
        (8, 150, "validation_error", "Session start time must be between 09:00 and 22:00."),
        (10, -10, "request_validation_error", "end_time must be greater than start_time."),
    ],
)
async def test_invalid_session_time_windows_are_rejected(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    start_hour: int,
    end_delta_minutes: int,
    expected_code: str,
    expected_message: str,
) -> None:
    movie = await create_movie(title=f"Invalid Window {start_hour}", duration_minutes=90)
    start_time, _ = build_session_window(start_hour=start_hour, duration_minutes=90)
    end_time = start_time + timedelta(minutes=end_delta_minutes)

    response = await client.post(
        f"{API_PREFIX}/admin/sessions",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "price": 180,
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == expected_code
    assert body["error"]["message"] == expected_message


@pytest.mark.asyncio
async def test_admin_rejects_invalid_session_prices_and_excessive_runtime_buffer(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
) -> None:
    movie = await create_movie(title="Validation Target", duration_minutes=120)
    start_time, _ = build_session_window(start_hour=10, duration_minutes=120)

    price_response = await client.post(
        f"{API_PREFIX}/admin/sessions",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(minutes=130)).isoformat(),
            "price": 180.555,
        },
    )
    assert price_response.status_code == 422
    assert price_response.json()["error"]["message"] == "price must have at most two decimal places."

    buffer_response = await client.post(
        f"{API_PREFIX}/admin/sessions",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": start_time.isoformat(),
            "end_time": (start_time + timedelta(minutes=190)).isoformat(),
            "price": 180,
        },
    )
    assert buffer_response.status_code == 422
    assert (
        buffer_response.json()["error"]["message"]
        == "Session slot cannot exceed the movie runtime by more than 60 minutes."
    )


@pytest.mark.asyncio
async def test_admin_session_payloads_reject_unexpected_fields(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
) -> None:
    movie = await create_movie(title="Strict Session Payload Movie", duration_minutes=120)
    start_time, end_time = build_session_window(start_hour=10, duration_minutes=150)

    create_response = await client.post(
        f"{API_PREFIX}/admin/sessions",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "price": 180,
            "hall_id": "vip",
        },
    )

    assert create_response.status_code == 422
    create_body = create_response.json()
    assert create_body["error"]["code"] == "request_validation_error"
    assert create_body["error"]["message"] == "Extra inputs are not permitted"

    update_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{ObjectId()}",
        headers=admin_auth["headers"],
        json={
            "price": 200,
            "available_seats": 10,
        },
    )

    assert update_response.status_code == 422
    update_body = update_response.json()
    assert update_body["error"]["code"] == "request_validation_error"
    assert update_body["error"]["message"] == "Extra inputs are not permitted"

    batch_response = await client.post(
        f"{API_PREFIX}/admin/sessions/batch",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "price": 180,
            "dates": [start_time.date().isoformat()],
            "total_seats": 120,
        },
    )

    assert batch_response.status_code == 422
    batch_body = batch_response.json()
    assert batch_body["error"]["code"] == "request_validation_error"
    assert batch_body["error"]["message"] == "Extra inputs are not permitted"


@pytest.mark.asyncio
async def test_admin_cannot_schedule_deactivated_movies(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
) -> None:
    movie = await create_movie(title="Archived Movie", status="deactivated")
    start_time, end_time = build_session_window(start_hour=18, duration_minutes=120)

    response = await client.post(
        f"{API_PREFIX}/admin/sessions",
        headers=admin_auth["headers"],
        json={
            "movie_id": movie["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "price": 180,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "Deactivated movies cannot be scheduled. Set the movie back to planned first."
    )


@pytest.mark.asyncio
async def test_session_update_is_rejected_when_it_creates_overlap(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Update Overlap Movie", duration_minutes=120)
    protected_session = await create_session(movie_id=movie["id"], start_hour=10, duration_minutes=150)
    editable_session = await create_session(movie_id=movie["id"], start_hour=14, duration_minutes=150)
    overlap_start, overlap_end = build_session_window(start_hour=11, duration_minutes=160)

    response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{editable_session['id']}",
        headers=admin_auth["headers"],
        json={
            "start_time": overlap_start.isoformat(),
            "end_time": overlap_end.isoformat(),
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Session overlaps with an existing session in the only hall."

    read_response = await client.get(
        f"{API_PREFIX}/admin/sessions/{editable_session['id']}",
        headers=admin_auth["headers"],
    )
    assert read_response.status_code == 200
    assert read_response.json()["data"]["id"] == editable_session["id"]
    assert protected_session["id"] != editable_session["id"]


@pytest.mark.asyncio
async def test_session_update_is_rejected_after_session_has_started(
    client: httpx.AsyncClient,
    database,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Started Session Update Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=15, duration_minutes=150)
    now = datetime.now(tz=timezone.utc)
    await database[DatabaseCollections.SESSIONS].update_one(
        {"_id": ObjectId(session["id"])},
        {
            "$set": {
                "status": "scheduled",
                "start_time": now - timedelta(minutes=30),
                "end_time": now + timedelta(minutes=90),
            }
        },
    )

    new_start, new_end = build_session_window(start_hour=18, duration_minutes=150)
    response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}",
        headers=admin_auth["headers"],
        json={
            "start_time": new_start.isoformat(),
            "end_time": new_end.isoformat(),
            "price": 310,
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Only future scheduled sessions can be edited."


@pytest.mark.asyncio
async def test_session_update_is_rejected_when_purchased_tickets_exist(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Ticketed Session Update Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=16, duration_minutes=150)

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 1,
            "seat_number": 1,
        },
    )
    assert purchase_response.status_code == 201

    new_start, new_end = build_session_window(start_hour=20, duration_minutes=150)
    response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}",
        headers=admin_auth["headers"],
        json={
            "start_time": new_start.isoformat(),
            "end_time": new_end.isoformat(),
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Sessions with purchased tickets cannot be edited. Cancel the session instead."


@pytest.mark.asyncio
async def test_session_cancellation_succeeds_and_repeated_cancellation_is_rejected(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Session Cancellation Movie", duration_minutes=100)
    session = await create_session(movie_id=movie["id"], start_hour=18, duration_minutes=140)

    cancel_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"

    repeat_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert repeat_response.status_code == 409
    body = repeat_response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Session has already been cancelled."


@pytest.mark.asyncio
async def test_session_cancellation_cascades_to_tickets_orders_and_seat_map(
    client: httpx.AsyncClient,
    database,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Cascade Cancel Session Movie", duration_minutes=100)
    session = await create_session(movie_id=movie["id"], start_hour=19, duration_minutes=140)

    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 3, "seat_number": 1},
                {"seat_row": 3, "seat_number": 2},
            ],
        },
    )
    assert purchase_response.status_code == 201
    order = purchase_response.json()["data"]

    cancel_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert cancel_response.status_code == 200, cancel_response.text
    cancelled_session = cancel_response.json()["data"]
    assert cancelled_session["status"] == "cancelled"
    assert cancelled_session["available_seats"] == cancelled_session["total_seats"]

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_order = await database[DatabaseCollections.ORDERS].find_one({"_id": ObjectId(order["id"])})
    stored_tickets = await database[DatabaseCollections.TICKETS].find({"order_id": order["id"]}).to_list(length=10)
    assert stored_session is not None
    assert stored_order is not None
    assert stored_session["status"] == "cancelled"
    assert stored_session["available_seats"] == stored_session["total_seats"]
    assert stored_order["status"] == "cancelled"
    assert {ticket["status"] for ticket in stored_tickets} == {"cancelled"}

    order_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=user_auth["headers"],
    )
    assert order_response.status_code == 200
    order_payload = order_response.json()["data"]
    assert order_payload["status"] == "cancelled"
    assert order_payload["active_tickets_count"] == 0
    assert order_payload["cancelled_tickets_count"] == 2

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_payload = seats_response.json()["data"]
    assert seats_payload["available_seats"] == seats_payload["total_seats"]
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 3 and seat["number"] == 1
    )["is_available"] is True
    assert next(
        seat for seat in seats_payload["seats"] if seat["row"] == 3 and seat["number"] == 2
    )["is_available"] is True

    repeat_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert repeat_response.status_code == 409
    assert repeat_response.json()["error"]["message"] == "Session has already been cancelled."


@pytest.mark.asyncio
async def test_session_cancellation_cascade_rolls_back_when_order_refresh_fails(
    client: httpx.AsyncClient,
    database,
    monkeypatch: pytest.MonkeyPatch,
    admin_auth: dict[str, object],
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Cascade Rollback Session Movie", duration_minutes=100)
    session = await create_session(movie_id=movie["id"], start_hour=20, duration_minutes=140)

    purchase_response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seats": [
                {"seat_row": 4, "seat_number": 1},
                {"seat_row": 4, "seat_number": 2},
            ],
        },
    )
    assert purchase_response.status_code == 201
    order = purchase_response.json()["data"]

    async def fail_update_order(
        self,
        order_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
        db_session=None,
    ) -> dict[str, object] | None:
        _ = (self, order_id, updates, updated_at, db_session)
        raise DatabaseException("Simulated session-cancellation order refresh failure.")

    monkeypatch.setattr(
        "app.repositories.orders.OrderRepository.update_order",
        fail_update_order,
    )

    cancel_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert cancel_response.status_code == 503
    assert cancel_response.json()["error"]["message"] == "Simulated session-cancellation order refresh failure."

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": ObjectId(session["id"])})
    stored_order = await database[DatabaseCollections.ORDERS].find_one({"_id": ObjectId(order["id"])})
    stored_tickets = await database[DatabaseCollections.TICKETS].find({"order_id": order["id"]}).to_list(length=10)
    assert stored_session is not None
    assert stored_order is not None
    assert stored_session["status"] == "scheduled"
    assert stored_session["available_seats"] == stored_session["total_seats"] - 2
    assert stored_order["status"] == "completed"
    assert {ticket["status"] for ticket in stored_tickets} == {"purchased"}
