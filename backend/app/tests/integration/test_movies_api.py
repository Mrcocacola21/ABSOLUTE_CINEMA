"""Integration tests for admin movie management flows."""

from __future__ import annotations

import httpx
import pytest
from bson import ObjectId

from app.db.collections import DatabaseCollections
from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
async def test_admin_can_create_list_read_and_update_movies(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    database,
) -> None:
    create_response = await client.post(
        f"{API_PREFIX}/admin/movies",
        headers=admin_auth["headers"],
        json={
            "title": "Arrival",
            "description": "First-contact drama",
            "duration_minutes": 116,
            "poster_url": None,
            "age_rating": "PG-13",
            "genres": ["Sci-Fi", "Drama"],
            "status": "planned",
        },
    )

    assert create_response.status_code == 201
    created_movie = create_response.json()["data"]
    movie_id = created_movie["id"]
    assert created_movie["title"] == "Arrival"
    assert created_movie["status"] == "planned"

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"title": "Arrival"})
    assert stored_movie is not None
    assert stored_movie["status"] == "planned"

    list_response = await client.get(f"{API_PREFIX}/admin/movies", headers=admin_auth["headers"])
    assert list_response.status_code == 200
    assert [movie["id"] for movie in list_response.json()["data"]] == [movie_id]

    read_response = await client.get(f"{API_PREFIX}/admin/movies/{movie_id}", headers=admin_auth["headers"])
    assert read_response.status_code == 200
    assert read_response.json()["data"]["id"] == movie_id

    update_response = await client.patch(
        f"{API_PREFIX}/admin/movies/{movie_id}",
        headers=admin_auth["headers"],
        json={
            "description": "Updated description",
            "genres": ["Drama", "Mystery", "Drama"],
            "poster_url": None,
        },
    )
    assert update_response.status_code == 200
    updated_movie = update_response.json()["data"]
    assert updated_movie["description"] == "Updated description"
    assert updated_movie["genres"] == ["Drama", "Mystery"]
    assert updated_movie["poster_url"] is None
    assert updated_movie["status"] == "planned"


@pytest.mark.asyncio
async def test_admin_can_create_and_update_movie_with_localized_fields_and_poster_url(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    database,
) -> None:
    localized_title = "\u041b\u044e\u0434\u0438\u043d\u0430-\u0431\u0435\u043d\u0437\u043e\u043f\u0438\u043b\u0430: \u0420\u0435\u0437\u0435 \u0410\u0440\u043a\u0430. \u041a\u0456\u043d\u043e"
    localized_description = (
        "\u041d\u0430\u0439\u043f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u0456\u0448\u0435 \u0430\u043d\u0456\u043c\u0435 "
        "\u00ab\u041b\u044e\u0434\u0438\u043d\u0430-\u0431\u0435\u043d\u0437\u043e\u043f\u0438\u043b\u0430\u00bb "
        "\u0432\u043f\u0435\u0440\u0448\u0435 \u043d\u0430 \u0432\u0435\u043b\u0438\u043a\u043e\u043c\u0443 \u0435\u043a\u0440\u0430\u043d\u0456. "
        "\u0414\u0435\u043d\u0434\u0436\u0456 \u0437\u0443\u0441\u0442\u0440\u0456\u0447\u0430\u0454 \u0420\u0435\u0437\u0435 "
        "\u0456 \u0432\u0441\u0442\u0443\u043f\u0430\u0454 \u0432 \u043d\u0435\u0431\u0435\u0437\u043f\u0435\u0447\u043d\u0443 \u0431\u0438\u0442\u0432\u0443."
    )
    localized_genres = [
        "\u0410\u043d\u0456\u043c\u0430\u0446\u0456\u044f",
        "\u0424\u0430\u043d\u0442\u0430\u0441\u0442\u0438\u043a\u0430",
        "\u0424\u0435\u043d\u0442\u0435\u0437\u0456",
        "\u041f\u0440\u0438\u0433\u043e\u0434\u0438",
    ]
    poster_url = "https://multiplex.ua/images/92/ae/92ae5046c523685edb03c8f9b0f2b854.jpeg"
    updated_poster_url = "https://example.com/posters/chainsaw-man-reze.jpg"

    create_response = await client.post(
        f"{API_PREFIX}/admin/movies",
        headers=admin_auth["headers"],
        json={
            "title": localized_title,
            "description": localized_description,
            "duration_minutes": 120,
            "poster_url": poster_url,
            "age_rating": "16+",
            "genres": localized_genres,
            "status": "planned",
        },
    )

    assert create_response.status_code == 201, create_response.text
    created_movie = create_response.json()["data"]
    assert created_movie["title"] == localized_title
    assert created_movie["poster_url"] == poster_url
    assert created_movie["genres"] == localized_genres
    assert created_movie["status"] == "planned"

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"_id": ObjectId(created_movie["id"])})
    assert stored_movie is not None
    assert stored_movie["poster_url"] == poster_url

    update_response = await client.patch(
        f"{API_PREFIX}/admin/movies/{created_movie['id']}",
        headers=admin_auth["headers"],
        json={
            "poster_url": updated_poster_url,
        },
    )

    assert update_response.status_code == 200, update_response.text
    updated_movie = update_response.json()["data"]
    assert updated_movie["poster_url"] == updated_poster_url


@pytest.mark.asyncio
async def test_admin_can_update_movie_status_when_no_future_sessions(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Status Update", status="planned")

    response = await client.patch(
        f"{API_PREFIX}/admin/movies/{movie['id']}",
        headers=admin_auth["headers"],
        json={"status": "deactivated"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "deactivated"

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"_id": ObjectId(movie["id"])})
    assert stored_movie is not None
    assert stored_movie["status"] == "deactivated"


@pytest.mark.asyncio
async def test_admin_cannot_create_movie_as_active_without_scheduling(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
) -> None:
    response = await client.post(
        f"{API_PREFIX}/admin/movies",
        headers=admin_auth["headers"],
        json={
            "title": "Invalid Active",
            "description": "Should fail",
            "duration_minutes": 100,
            "poster_url": None,
            "age_rating": "PG",
            "genres": ["Drama"],
            "status": "active",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "New movies must start as planned or deactivated. Active status is assigned automatically after scheduling."
    )


@pytest.mark.asyncio
async def test_movie_becomes_active_after_session_creation_and_deactivates_after_cancellation(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Lifecycle Demo", status="planned")

    created_session = await create_session(movie_id=movie["id"], start_hour=10, duration_minutes=180)
    assert created_session["movie"]["status"] == "active"

    admin_movie_response = await client.get(
        f"{API_PREFIX}/admin/movies/{movie['id']}",
        headers=admin_auth["headers"],
    )
    assert admin_movie_response.status_code == 200
    assert admin_movie_response.json()["data"]["status"] == "active"

    cancel_response = await client.patch(
        f"{API_PREFIX}/admin/sessions/{created_session['id']}/cancel",
        headers=admin_auth["headers"],
    )
    assert cancel_response.status_code == 200

    refreshed_movie_response = await client.get(
        f"{API_PREFIX}/admin/movies/{movie['id']}",
        headers=admin_auth["headers"],
    )
    assert refreshed_movie_response.status_code == 200
    assert refreshed_movie_response.json()["data"]["status"] == "deactivated"


@pytest.mark.asyncio
async def test_admin_can_deactivate_movie(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Blade Runner 2049", status="planned")

    response = await client.patch(
        f"{API_PREFIX}/admin/movies/{movie['id']}/deactivate",
        headers=admin_auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "deactivated"

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"_id": ObjectId(movie["id"])})
    assert stored_movie is not None
    assert stored_movie["status"] == "deactivated"


@pytest.mark.asyncio
async def test_admin_can_return_deactivated_movie_to_planned(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Return Me", status="deactivated")

    response = await client.patch(
        f"{API_PREFIX}/admin/movies/{movie['id']}",
        headers=admin_auth["headers"],
        json={"status": "planned"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "planned"

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"_id": ObjectId(movie["id"])})
    assert stored_movie is not None
    assert stored_movie["status"] == "planned"


@pytest.mark.asyncio
async def test_movie_delete_succeeds_when_movie_has_no_sessions(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Delete Me", status="planned")

    response = await client.delete(f"{API_PREFIX}/admin/movies/{movie['id']}", headers=admin_auth["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"id": movie["id"], "deleted": True}

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"_id": ObjectId(movie["id"])})
    assert stored_movie is None


@pytest.mark.asyncio
async def test_movie_delete_is_rejected_when_sessions_exist(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Protected Movie", status="planned")
    session = await create_session(movie_id=movie["id"], start_hour=10, duration_minutes=180)
    assert session["movie_id"] == movie["id"]

    response = await client.delete(f"{API_PREFIX}/admin/movies/{movie['id']}", headers=admin_auth["headers"])

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Movies used in sessions cannot be deleted. Deactivate the movie instead."


@pytest.mark.asyncio
async def test_public_movies_catalog_can_include_non_active_movies_when_requested(
    client: httpx.AsyncClient,
    create_movie,
    create_session,
) -> None:
    active_movie = await create_movie(title="Public Active", status="planned")
    _ = await create_session(movie_id=active_movie["id"], start_hour=10, duration_minutes=180)
    planned_movie = await create_movie(title="Public Planned", status="planned")
    deactivated_movie = await create_movie(title="Public Archived", status="deactivated")

    default_response = await client.get(f"{API_PREFIX}/movies")
    assert default_response.status_code == 200
    default_ids = [movie["id"] for movie in default_response.json()["data"]]
    assert active_movie["id"] in default_ids
    assert planned_movie["id"] not in default_ids
    assert deactivated_movie["id"] not in default_ids

    catalog_response = await client.get(f"{API_PREFIX}/movies", params={"include_inactive": "true"})
    assert catalog_response.status_code == 200
    catalog_ids = [movie["id"] for movie in catalog_response.json()["data"]]
    assert active_movie["id"] in catalog_ids
    assert planned_movie["id"] in catalog_ids
    assert deactivated_movie["id"] in catalog_ids


@pytest.mark.asyncio
async def test_public_movie_details_can_include_planned_movies_when_requested(
    client: httpx.AsyncClient,
    create_movie,
) -> None:
    planned_movie = await create_movie(title="Planned Title", status="planned")

    default_response = await client.get(f"{API_PREFIX}/movies/{planned_movie['id']}")
    assert default_response.status_code == 404

    catalog_response = await client.get(
        f"{API_PREFIX}/movies/{planned_movie['id']}",
        params={"include_inactive": "true"},
    )
    assert catalog_response.status_code == 200
    assert catalog_response.json()["data"]["id"] == planned_movie["id"]
    assert catalog_response.json()["data"]["status"] == "planned"


@pytest.mark.asyncio
async def test_movie_routes_return_404_for_missing_movies_and_422_for_invalid_identifiers(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
) -> None:
    missing_movie_id = str(ObjectId())

    public_missing_response = await client.get(f"{API_PREFIX}/movies/{missing_movie_id}")
    assert public_missing_response.status_code == 404
    public_missing_body = public_missing_response.json()
    assert public_missing_body["success"] is False
    assert public_missing_body["error"]["code"] == "not_found"
    assert public_missing_body["error"]["message"] == "Movie was not found."

    admin_missing_response = await client.get(
        f"{API_PREFIX}/admin/movies/{missing_movie_id}",
        headers=admin_auth["headers"],
    )
    assert admin_missing_response.status_code == 404
    admin_missing_body = admin_missing_response.json()
    assert admin_missing_body["success"] is False
    assert admin_missing_body["error"]["code"] == "not_found"
    assert admin_missing_body["error"]["message"] == "Movie was not found."

    invalid_public_response = await client.get(f"{API_PREFIX}/movies/not-a-valid-object-id")
    assert invalid_public_response.status_code == 422
    invalid_public_body = invalid_public_response.json()
    assert invalid_public_body["success"] is False
    assert invalid_public_body["error"]["code"] == "validation_error"
    assert invalid_public_body["error"]["message"] == "Invalid MongoDB identifier format."
