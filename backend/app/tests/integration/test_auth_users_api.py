"""Integration tests for authentication and user profile flows."""

from __future__ import annotations

import httpx
import pytest

from app.db.collections import DatabaseCollections

from app.tests.integration.conftest import API_PREFIX, DEFAULT_PASSWORD


@pytest.mark.asyncio
async def test_successful_registration_persists_hashed_user(
    client: httpx.AsyncClient,
    database,
) -> None:
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": "fresh@example.com",
            "name": "Fresh User",
            "password": DEFAULT_PASSWORD,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "fresh@example.com"
    assert "password_hash" not in body["data"]

    stored_user = await database[DatabaseCollections.USERS].find_one({"email": "fresh@example.com"})
    assert stored_user is not None
    assert stored_user["password_hash"] != DEFAULT_PASSWORD
    assert stored_user["role"] == "user"


@pytest.mark.asyncio
async def test_registration_normalizes_email_and_name_whitespace(
    client: httpx.AsyncClient,
    database,
) -> None:
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": "FreshUser@Example.COM",
            "name": "  Fresh   User  ",
            "password": DEFAULT_PASSWORD,
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["email"] == "freshuser@example.com"
    assert body["name"] == "Fresh User"

    stored_user = await database[DatabaseCollections.USERS].find_one({"email": "freshuser@example.com"})
    assert stored_user is not None
    assert stored_user["name"] == "Fresh User"


@pytest.mark.asyncio
async def test_duplicate_email_registration_returns_conflict(
    register_user,
    database,
) -> None:
    first_response = await register_user(email="duplicate@example.com", name="First User")
    assert first_response.status_code == 201

    second_response = await register_user(email="duplicate@example.com", name="Second User")

    assert second_response.status_code == 409
    body = second_response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "A user with this email already exists."

    count = await database[DatabaseCollections.USERS].count_documents({"email": "duplicate@example.com"})
    assert count == 1


@pytest.mark.asyncio
async def test_successful_login_returns_access_token(
    register_user,
    login_user,
) -> None:
    register_response = await register_user(email="login@example.com", name="Login User")
    assert register_response.status_code == 201

    response = await login_user(email="login@example.com")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["access_token"]
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_auth_error(
    register_user,
    login_user,
) -> None:
    register_response = await register_user(email="wrong-password@example.com", name="Wrong Password User")
    assert register_response.status_code == 201

    response = await login_user(email="wrong-password@example.com", password="IncorrectPassword123")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Incorrect email or password."


@pytest.mark.asyncio
async def test_users_me_returns_authenticated_profile(user_auth: dict[str, object], client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/users/me", headers=user_auth["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "user@example.com"
    assert body["data"]["role"] == "user"


@pytest.mark.asyncio
async def test_users_me_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/users/me")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "authentication_error"
    assert body["error"]["message"] == "Authentication is required to access this resource."


@pytest.mark.asyncio
async def test_users_me_update_normalizes_name_and_email(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
    database,
) -> None:
    response = await client.patch(
        f"{API_PREFIX}/users/me",
        headers=user_auth["headers"],
        json={
            "name": "  Updated   User  ",
            "email": "NEW-EMAIL@EXAMPLE.COM",
            "current_password": DEFAULT_PASSWORD,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["name"] == "Updated User"
    assert payload["email"] == "new-email@example.com"

    stored_user = await database[DatabaseCollections.USERS].find_one({"_id": payload["id"]})
    if stored_user is None:
        stored_user = await database[DatabaseCollections.USERS].find_one({"email": "new-email@example.com"})
    assert stored_user is not None
    assert stored_user["name"] == "Updated User"
    assert stored_user["email"] == "new-email@example.com"


@pytest.mark.asyncio
async def test_users_me_update_rejects_reusing_current_password(
    client: httpx.AsyncClient,
    user_auth: dict[str, object],
) -> None:
    response = await client.patch(
        f"{API_PREFIX}/users/me",
        headers=user_auth["headers"],
        json={
            "password": DEFAULT_PASSWORD,
            "current_password": DEFAULT_PASSWORD,
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_error"
    assert body["error"]["message"] == "New password must be different from current_password."
