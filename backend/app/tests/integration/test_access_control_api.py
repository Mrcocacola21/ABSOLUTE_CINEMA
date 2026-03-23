"""Integration tests for role and access control behavior."""

from __future__ import annotations

import httpx
import pytest

from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        f"{API_PREFIX}/admin/movies",
        f"{API_PREFIX}/admin/sessions",
        f"{API_PREFIX}/admin/tickets",
        f"{API_PREFIX}/admin/users",
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
    assert response.json()["detail"] == "Not authenticated"
