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
            "is_active": True,
        },
    )

    assert create_response.status_code == 201
    created_movie = create_response.json()["data"]
    movie_id = created_movie["id"]
    assert created_movie["title"] == "Arrival"

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"title": "Arrival"})
    assert stored_movie is not None
    assert stored_movie["is_active"] is True

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


@pytest.mark.asyncio
async def test_admin_can_deactivate_movie(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Blade Runner 2049")

    response = await client.patch(
        f"{API_PREFIX}/admin/movies/{movie['id']}/deactivate",
        headers=admin_auth["headers"],
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False

    stored_movie = await database[DatabaseCollections.MOVIES].find_one({"_id": ObjectId(movie["id"])})
    assert stored_movie is not None
    assert stored_movie["is_active"] is False


@pytest.mark.asyncio
async def test_movie_delete_succeeds_when_movie_has_no_sessions(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    create_movie,
    database,
) -> None:
    movie = await create_movie(title="Delete Me")

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
    movie = await create_movie(title="Protected Movie")
    session = await create_session(movie_id=movie["id"], start_hour=10, duration_minutes=180)
    assert session["movie_id"] == movie["id"]

    response = await client.delete(f"{API_PREFIX}/admin/movies/{movie['id']}", headers=admin_auth["headers"])

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Movies used in sessions cannot be deleted. Deactivate the movie instead."
