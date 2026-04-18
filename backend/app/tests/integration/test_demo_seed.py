"""Integration tests for the explicit demo-data seeding flow."""

from __future__ import annotations

import httpx
import pytest

from app.db.collections import DatabaseCollections
from app.seeds.demo_dataset import DEMO_ADMIN_EMAIL, DEMO_SHARED_PASSWORD
from app.seeds.demo_seed import seed_demo_database
from app.tests.integration.conftest import API_PREFIX


@pytest.mark.asyncio
async def test_demo_seed_command_is_repeatable_and_creates_login_ready_demo_data(
    client: httpx.AsyncClient,
    database,
    auth_headers,
) -> None:
    first_summary = await seed_demo_database(reset=True, database=database)
    second_summary = await seed_demo_database(reset=False, database=database)

    assert first_summary.counts == second_summary.counts == {
        "users": 5,
        "movies": 10,
        "sessions": 20,
        "orders": 9,
        "tickets": 20,
    }

    counts = {
        "users": await database[DatabaseCollections.USERS].count_documents({}),
        "movies": await database[DatabaseCollections.MOVIES].count_documents({}),
        "sessions": await database[DatabaseCollections.SESSIONS].count_documents({}),
        "orders": await database[DatabaseCollections.ORDERS].count_documents({}),
        "tickets": await database[DatabaseCollections.TICKETS].count_documents({}),
    }
    assert counts == first_summary.counts

    login_response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={
            "username": DEMO_ADMIN_EMAIL,
            "password": DEMO_SHARED_PASSWORD,
        },
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["data"]["access_token"]

    profile_response = await client.get(
        f"{API_PREFIX}/users/me",
        headers=auth_headers(token),
    )
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()["data"]
    assert profile["email"] == DEMO_ADMIN_EMAIL
    assert profile["role"] == "admin"

    seeded_movie = await database[DatabaseCollections.MOVIES].find_one({"title.en": "Spirited Away"})
    assert seeded_movie is not None
    assert seeded_movie["poster_url"] == "/demo-posters/spirited-away.svg"
