"""Integration tests for admin session management flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

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
@pytest.mark.parametrize(
    ("start_hour", "end_delta_minutes", "expected_code", "expected_message"),
    [
        (8, 150, "validation_error", "Session start time must be between 09:00 and 22:00."),
        (10, -10, "request_validation_error", "Request validation failed."),
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

