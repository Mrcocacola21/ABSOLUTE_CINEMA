"""Integration tests for role and access control behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from bson import ObjectId
from jose import jwt

from app.core.config import get_settings
from app.db.collections import DatabaseCollections

from app.tests.integration.conftest import API_PREFIX, build_localized_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        f"{API_PREFIX}/admin/movies",
        f"{API_PREFIX}/admin/sessions",
        f"{API_PREFIX}/admin/tickets",
        f"{API_PREFIX}/admin/users",
        f"{API_PREFIX}/admin/attendance",
        f"{API_PREFIX}/admin/attendance/sessions/{ObjectId()}",
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
                "title": build_localized_text("Заборонений фільм", en="Forbidden Movie"),
                "description": build_localized_text(
                    "Не має створюватися звичайним користувачем.",
                    en="Should not be created by a non-admin user.",
                ),
                "duration_minutes": 120,
                "poster_url": None,
                "age_rating": "PG-13",
                "genres": ["drama"],
                "is_active": True,
            },
        ),
        await client.patch(
            f"{API_PREFIX}/admin/movies/{movie['id']}",
            headers=user_auth["headers"],
            json={"title": {"en": "Still Forbidden"}},
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
    create_authenticated_user,
) -> None:
    newest_user = await create_authenticated_user(email="newest-admin-list@example.com", name="Newest Admin List")

    response = await client.get(f"{API_PREFIX}/admin/users", headers=admin_auth["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["email"] == newest_user["user"]["email"]
    assert body["data"][1]["email"] == "admin@example.com"
    assert all("password" not in user for user in body["data"])
    assert all("password_hash" not in user for user in body["data"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        f"{API_PREFIX}/admin/users",
        f"{API_PREFIX}/admin/tickets",
        f"{API_PREFIX}/admin/attendance",
        f"{API_PREFIX}/admin/attendance/sessions/{ObjectId()}",
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
async def test_expired_tokens_return_standardized_401(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    auth_headers,
) -> None:
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": user_auth["user"]["id"],
            "email": user_auth["user"]["email"],
            "role": user_auth["user"]["role"],
            "exp": int((datetime.now(tz=timezone.utc) - timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        f"{API_PREFIX}/users/me",
        headers=auth_headers(expired_token),
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Invalid or expired access token."


@pytest.mark.asyncio
async def test_token_with_invalid_subject_format_returns_standardized_401(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    auth_headers,
) -> None:
    settings = get_settings()
    invalid_subject_token = jwt.encode(
        {
            "sub": "not-a-valid-object-id",
            "email": user_auth["user"]["email"],
            "role": user_auth["user"]["role"],
            "exp": int((datetime.now(tz=timezone.utc) + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        f"{API_PREFIX}/users/me",
        headers=auth_headers(invalid_subject_token),
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Invalid or expired access token."


@pytest.mark.asyncio
async def test_token_for_deleted_user_returns_standardized_401(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    database,
) -> None:
    await database[DatabaseCollections.USERS].delete_one({"_id": ObjectId(user_auth["user"]["id"])})

    response = await client.get(
        f"{API_PREFIX}/users/me",
        headers=user_auth["headers"],
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Authenticated user no longer exists."


@pytest.mark.asyncio
async def test_token_for_inactive_user_returns_standardized_401(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    database,
) -> None:
    await database[DatabaseCollections.USERS].update_one(
        {"_id": ObjectId(user_auth["user"]["id"])},
        {"$set": {"is_active": False}},
    )

    response = await client.get(
        f"{API_PREFIX}/users/me",
        headers=user_auth["headers"],
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "This account is inactive."


@pytest.mark.asyncio
async def test_inactive_admin_cannot_access_admin_endpoint_with_existing_token(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
    database,
) -> None:
    await database[DatabaseCollections.USERS].update_one(
        {"_id": ObjectId(admin_auth["user"]["id"])},
        {"$set": {"is_active": False}},
    )

    response = await client.get(
        f"{API_PREFIX}/admin/users",
        headers=admin_auth["headers"],
    )

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "This account is inactive."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", f"{API_PREFIX}/tickets/me", None),
        ("get", f"{API_PREFIX}/users/me/orders", None),
        (
            "post",
            f"{API_PREFIX}/tickets/purchase",
            {
                "session_id": str(ObjectId()),
                "seat_row": 1,
                "seat_number": 1,
            },
        ),
        (
            "post",
            f"{API_PREFIX}/orders/purchase",
            {
                "session_id": str(ObjectId()),
                "seats": [{"seat_row": 1, "seat_number": 1}],
            },
        ),
        ("patch", f"{API_PREFIX}/tickets/{ObjectId()}/cancel", None),
        ("patch", f"{API_PREFIX}/orders/{ObjectId()}/cancel", None),
    ],
)
async def test_unauthenticated_booking_endpoints_return_standardized_401(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    request = getattr(client, method)
    response = await request(path, json=payload) if payload is not None else await request(path)

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Authentication is required to access this resource."
