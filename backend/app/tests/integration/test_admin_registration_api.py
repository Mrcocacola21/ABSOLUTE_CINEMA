"""Integration tests for admin registration bootstrap and admin access acquisition."""

from __future__ import annotations

import httpx
import pytest

from app.db.collections import DatabaseCollections
from app.security.jwt import decode_access_token
from app.tests.integration.conftest import API_PREFIX, ADMIN_EMAIL, DEFAULT_PASSWORD


@pytest.mark.asyncio
async def test_configured_admin_email_registers_as_admin_and_ignores_client_role(
    client: httpx.AsyncClient,
    database,
) -> None:
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": ADMIN_EMAIL.upper(),
            "name": "Bootstrap Admin",
            "password": DEFAULT_PASSWORD,
            "role": "user",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == ADMIN_EMAIL
    assert body["data"]["role"] == "admin"

    stored_user = await database[DatabaseCollections.USERS].find_one({"email": ADMIN_EMAIL})
    assert stored_user is not None
    assert stored_user["email"] == ADMIN_EMAIL
    assert stored_user["role"] == "admin"


@pytest.mark.asyncio
async def test_regular_email_cannot_self_assign_admin_role_during_registration(
    client: httpx.AsyncClient,
    database,
) -> None:
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": "self-promoted@example.com",
            "name": "Self Promoted User",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "self-promoted@example.com"
    assert body["data"]["role"] == "user"

    stored_user = await database[DatabaseCollections.USERS].find_one(
        {"email": "self-promoted@example.com"}
    )
    assert stored_user is not None
    assert stored_user["role"] == "user"


@pytest.mark.asyncio
async def test_duplicate_admin_registration_uses_same_conflict_rule(
    register_user,
    database,
) -> None:
    first_response = await register_user(email=ADMIN_EMAIL, name="First Admin")
    assert first_response.status_code == 201
    assert first_response.json()["data"]["role"] == "admin"

    second_response = await register_user(email=ADMIN_EMAIL.upper(), name="Second Admin Attempt")

    assert second_response.status_code == 409
    body = second_response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "A user with this email already exists."

    count = await database[DatabaseCollections.USERS].count_documents({"email": ADMIN_EMAIL})
    assert count == 1


@pytest.mark.asyncio
async def test_admin_can_log_in_receive_admin_token_and_access_admin_endpoint(
    client: httpx.AsyncClient,
    register_user,
    login_user,
    auth_headers,
) -> None:
    register_response = await register_user(email=ADMIN_EMAIL, name="Admin Login User")
    assert register_response.status_code == 201
    assert register_response.json()["data"]["role"] == "admin"

    login_response = await login_user(email=ADMIN_EMAIL)

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["success"] is True
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["expires_in"] > 0
    assert body["data"]["access_token"]

    token = body["data"]["access_token"]
    payload = decode_access_token(token)
    assert payload.email == ADMIN_EMAIL
    assert payload.role == "admin"
    assert payload.sub

    admin_response = await client.get(
        f"{API_PREFIX}/admin/users",
        headers=auth_headers(token),
    )

    assert admin_response.status_code == 200
    admin_body = admin_response.json()
    assert admin_body["success"] is True
    assert admin_body["data"][0]["email"] == ADMIN_EMAIL
    assert admin_body["data"][0]["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_endpoint_requires_admin_role_and_authentication(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
) -> None:
    user_response = await client.get(
        f"{API_PREFIX}/admin/users",
        headers=user_auth["headers"],
    )

    assert user_response.status_code == 403
    user_body = user_response.json()
    assert user_body["success"] is False
    assert user_body["error"]["code"] == "authorization_error"
    assert user_body["error"]["message"] == "Administrator role is required."

    anonymous_response = await client.get(f"{API_PREFIX}/admin/users")

    assert anonymous_response.status_code == 401
    anonymous_body = anonymous_response.json()
    assert anonymous_body["success"] is False
    assert anonymous_body["error"]["code"] == "authentication_error"
    assert anonymous_body["error"]["message"] == "Authentication is required to access this resource."
