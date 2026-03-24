"""Integration tests for role and access control behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from jose import jwt

from app.core.config import get_settings

from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        f"{API_PREFIX}/admin/movies",
        f"{API_PREFIX}/admin/sessions",
        f"{API_PREFIX}/admin/tickets",
        f"{API_PREFIX}/admin/users",
        f"{API_PREFIX}/admin/attendance",
    ],
)
async def test_non_admin_cannot_access_admin_endpoints(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    path: str,
) -> None:
    response = await client.get(path, headers=user_auth["headers"])

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authorization_error"
    assert body["error"]["message"] == "Administrator role is required."


@pytest.mark.asyncio
async def test_non_admin_cannot_mutate_admin_movies_or_sessions(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Protected Admin Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=20, duration_minutes=160)

    responses = [
        await client.post(
            f"{API_PREFIX}/admin/movies",
            headers=user_auth["headers"],
            json={
                "title": "Forbidden Movie",
                "description": "Should not be created by a non-admin user.",
                "duration_minutes": 120,
                "poster_url": None,
                "age_rating": "PG-13",
                "genres": ["Drama"],
                "is_active": True,
            },
        ),
        await client.patch(
            f"{API_PREFIX}/admin/movies/{movie['id']}",
            headers=user_auth["headers"],
            json={"title": "Still Forbidden"},
        ),
        await client.patch(
            f"{API_PREFIX}/admin/movies/{movie['id']}/deactivate",
            headers=user_auth["headers"],
        ),
        await client.delete(
            f"{API_PREFIX}/admin/movies/{movie['id']}",
            headers=user_auth["headers"],
        ),
        await client.post(
            f"{API_PREFIX}/admin/sessions",
            headers=user_auth["headers"],
            json={
                "movie_id": movie["id"],
                "start_time": session["start_time"],
                "end_time": session["end_time"],
                "price": 200,
            },
        ),
        await client.patch(
            f"{API_PREFIX}/admin/sessions/{session['id']}",
            headers=user_auth["headers"],
            json={"price": 260},
        ),
        await client.patch(
            f"{API_PREFIX}/admin/sessions/{session['id']}/cancel",
            headers=user_auth["headers"],
        ),
        await client.delete(
            f"{API_PREFIX}/admin/sessions/{session['id']}",
            headers=user_auth["headers"],
        ),
    ]

    for response in responses:
        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "authorization_error"
        assert body["error"]["message"] == "Administrator role is required."


@pytest.mark.asyncio
async def test_admin_can_access_admin_endpoints(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
) -> None:
    response = await client.get(f"{API_PREFIX}/admin/users", headers=admin_auth["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["email"] == "admin@example.com"
    assert "password_hash" not in body["data"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        f"{API_PREFIX}/admin/users",
        f"{API_PREFIX}/admin/tickets",
        f"{API_PREFIX}/admin/attendance",
    ],
)
async def test_unauthenticated_admin_endpoints_return_standardized_401(
    client: httpx.AsyncClient,
    path: str,
) -> None:
    response = await client.get(path)

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Authentication is required to access this resource."


@pytest.mark.asyncio
async def test_invalid_tokens_return_standardized_401(
    client: httpx.AsyncClient,
    auth_headers,
) -> None:
    invalid_token_response = await client.get(
        f"{API_PREFIX}/users/me",
        headers=auth_headers("not-a-valid-jwt"),
    )

    assert invalid_token_response.status_code == 401
    invalid_body = invalid_token_response.json()
    assert invalid_body["success"] is False
    assert invalid_body["error"]["code"] == "authentication_error"
    assert invalid_body["error"]["message"] == "Invalid or expired access token."

    settings = get_settings()
    malformed_payload_token = jwt.encode(
        {
            "email": "broken@example.com",
            "role": "user",
            "exp": int((datetime.now(tz=timezone.utc) + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    malformed_payload_response = await client.get(
        f"{API_PREFIX}/users/me",
        headers=auth_headers(malformed_payload_token),
    )

    assert malformed_payload_response.status_code == 401
    malformed_body = malformed_payload_response.json()
    assert malformed_body["success"] is False
    assert malformed_body["error"]["code"] == "authentication_error"
    assert malformed_body["error"]["message"] == "Invalid or expired access token."


@pytest.mark.asyncio
async def test_unauthenticated_user_cannot_purchase_tickets(
    client: httpx.AsyncClient,
    create_movie,
    create_session,
) -> None:
    movie = await create_movie(title="Protected Purchase Movie", duration_minutes=120)
    session = await create_session(movie_id=movie["id"], start_hour=19, duration_minutes=160)

    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        json={
            "session_id": session["id"],
            "seat_row": 1,
            "seat_number": 1,
        },
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Authentication is required to access this resource."
