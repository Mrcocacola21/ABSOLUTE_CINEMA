"""Integration tests for public schedule and seat availability flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId

from app.db.collections import DatabaseCollections

from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
async def test_public_schedule_supports_listing_sorting_filtering_and_excludes_cancelled_sessions(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    first_movie = await create_movie(title="Alpha Movie", duration_minutes=120)
    second_movie = await create_movie(title="Beta Movie", duration_minutes=120)
    first_session = await create_session(movie_id=first_movie["id"], start_hour=10, duration_minutes=160)
    second_session = await create_session(movie_id=second_movie["id"], start_hour=14, duration_minutes=160)

    cancel_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{first_session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert cancel_response.status_code == 200

    schedule_response = await client.get(
        f"{API_PREFIX}/schedule",
        params={"sort_by": "start_time", "sort_order": "desc", "limit": 20, "offset": 0},
    )
    assert schedule_response.status_code == 200
    schedule_items = schedule_response.json()["data"]
    assert [item["id"] for item in schedule_items] == [second_session["id"]]
    assert schedule_items[0]["movie_title"] == second_movie["title"]
    assert schedule_items[0]["genres"] == second_movie["genres"]

    filter_response = await client.get(
        f"{API_PREFIX}/schedule",
        params={
            "sort_by": "start_time",
            "sort_order": "asc",
            "movie_id": second_movie["id"],
            "limit": 20,
            "offset": 0,
        },
    )
    assert filter_response.status_code == 200
    filtered_items = filter_response.json()["data"]
    assert [item["movie_id"] for item in filtered_items] == [second_movie["id"]]
    assert filtered_items[0]["movie_title"] == second_movie["title"]


@pytest.mark.asyncio
async def test_session_details_and_seats_endpoints_return_expected_structure(
    client: httpx.AsyncClient,
    create_movie,
    create_session,
    user_auth: dict[str, object],
) -> None:
    movie = await create_movie(title="Seat Map Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=11, duration_minutes=150, price=210)

    purchase_response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=user_auth["headers"],
        json={
            "session_id": session["id"],
            "seat_row": 2,
            "seat_number": 3,
        },
    )
    assert purchase_response.status_code == 201

    details_response = await client.get(f"{API_PREFIX}/schedule/{session['id']}")
    assert details_response.status_code == 200
    details = details_response.json()["data"]
    assert details["id"] == session["id"]
    assert details["movie"]["id"] == movie["id"]
    assert details["movie"]["title"] == movie["title"]
    assert details["movie"]["genres"] == movie["genres"]
    assert details["available_seats"] == details["total_seats"] - 1

    seats_response = await client.get(f"{API_PREFIX}/sessions/{session['id']}/seats")
    assert seats_response.status_code == 200
    seats_body = seats_response.json()["data"]
    assert seats_body["session_id"] == session["id"]
    assert seats_body["available_seats"] == seats_body["total_seats"] - 1
    occupied_seat = next(seat for seat in seats_body["seats"] if seat["row"] == 2 and seat["number"] == 3)
    free_seat = next(seat for seat in seats_body["seats"] if seat["row"] == 1 and seat["number"] == 1)
    assert occupied_seat["is_available"] is False
    assert free_seat["is_available"] is True


@pytest.mark.asyncio
async def test_past_scheduled_sessions_are_not_returned_in_public_schedule_after_completion_sync(
    client: httpx.AsyncClient,
    database,
    create_movie,
) -> None:
    movie = await create_movie(title="Past Session Movie", duration_minutes=120)
    now = datetime.now(tz=timezone.utc)
    session_document = {
        "movie_id": movie["id"],
        "start_time": now - timedelta(hours=4),
        "end_time": now - timedelta(hours=2),
        "price": 180,
        "status": "scheduled",
        "total_seats": 96,
        "available_seats": 96,
        "created_at": now - timedelta(days=1),
        "updated_at": None,
    }
    insert_result = await database[DatabaseCollections.SESSIONS].insert_one(session_document)
    session_id = str(insert_result.inserted_id)

    schedule_response = await client.get(
        f"{API_PREFIX}/schedule",
        params={"sort_by": "start_time", "sort_order": "asc", "limit": 20, "offset": 0},
    )
    assert schedule_response.status_code == 200
    assert schedule_response.json()["data"] == []

    stored_session = await database[DatabaseCollections.SESSIONS].find_one({"_id": insert_result.inserted_id})
    assert stored_session is not None
    assert stored_session["status"] == "completed"

    details_response = await client.get(f"{API_PREFIX}/schedule/{session_id}")
    assert details_response.status_code == 200
    assert details_response.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_public_schedule_tolerates_legacy_localized_movie_documents(
    client: httpx.AsyncClient,
    database,
) -> None:
    now = datetime.now(tz=timezone.utc)
    movie_result = await database[DatabaseCollections.MOVIES].insert_one(
        {
            "title": {"uk": "TEST", "en": "TEST"},
            "description": {"uk": "TEST", "en": "TEST"},
            "duration_minutes": 100,
            "poster_url": None,
            "age_rating": "PG",
            "genres": ["drama"],
            "status": "planned",
            "created_at": now - timedelta(days=1),
            "updated_at": None,
        }
    )
    movie_id = str(movie_result.inserted_id)
    session_result = await database[DatabaseCollections.SESSIONS].insert_one(
        {
            "movie_id": movie_id,
            "start_time": now + timedelta(hours=3),
            "end_time": now + timedelta(hours=5),
            "price": 180,
            "status": "scheduled",
            "total_seats": 96,
            "available_seats": 96,
            "created_at": now - timedelta(days=1),
            "updated_at": None,
        }
    )

    response = await client.get(
        f"{API_PREFIX}/schedule",
        params={"sort_by": "start_time", "sort_order": "asc", "limit": 20, "offset": 0},
    )

    assert response.status_code == 200
    schedule_items = response.json()["data"]
    assert [item["id"] for item in schedule_items] == [str(session_result.inserted_id)]
    assert schedule_items[0]["movie_title"] == {"uk": "TEST", "en": "TEST"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "expected_message"),
    [
        ({"sort_by": "unsupported"}, "Unsupported sort field."),
        ({"sort_order": "sideways"}, "Unsupported sort order."),
    ],
)
async def test_schedule_rejects_invalid_query_parameters(
    client: httpx.AsyncClient,
    params: dict[str, str],
    expected_message: str,
) -> None:
    response = await client.get(
        f"{API_PREFIX}/schedule",
        params={**params, "limit": 20, "offset": 0},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"] == expected_message


@pytest.mark.asyncio
async def test_session_detail_routes_return_404_for_missing_session(
    client: httpx.AsyncClient,
) -> None:
    missing_session_id = str(ObjectId())

    details_response = await client.get(f"{API_PREFIX}/schedule/{missing_session_id}")
    assert details_response.status_code == 404
    details_body = details_response.json()
    assert details_body["success"] is False
    assert details_body["error"]["code"] == "not_found"
    assert details_body["error"]["message"] == "Session was not found."

    seats_response = await client.get(f"{API_PREFIX}/sessions/{missing_session_id}/seats")
    assert seats_response.status_code == 404
    seats_body = seats_response.json()
    assert seats_body["success"] is False
    assert seats_body["error"]["code"] == "not_found"
    assert seats_body["error"]["message"] == "Session was not found."
