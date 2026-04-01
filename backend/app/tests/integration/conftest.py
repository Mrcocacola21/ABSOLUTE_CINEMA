"""Shared fixtures for backend integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from pymongo import MongoClient

from app.core.config import get_settings
from app.db.collections import DatabaseCollections

API_PREFIX = "/api/v1"
KYIV_TIMEZONE = ZoneInfo("Europe/Kyiv")
DEFAULT_PASSWORD = "CinemaPass123"
ADMIN_EMAIL = "admin@example.com"
USER_EMAIL = "user@example.com"
DEFAULT_TEST_MONGODB_URI = "mongodb://127.0.0.1:27017/?replicaSet=rs0&directConnection=true"
DEFAULT_TEST_DB_NAME = "cinema_showcase_test"
UNSAFE_DATABASE_NAMES = {"cinema_showcase"}


def build_localized_text(value: str, *, en: str | None = None) -> dict[str, str]:
    """Build a localized text payload for tests."""
    return {
        "uk": value,
        "en": en or value,
    }


def build_session_window(
    *,
    day_offset: int = 1,
    start_hour: int = 10,
    duration_minutes: int = 120,
) -> tuple[datetime, datetime]:
    """Build a future session window in the cinema timezone."""
    now = datetime.now(KYIV_TIMEZONE)
    start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
    if start <= now:
        start += timedelta(days=1)
    end = start + timedelta(minutes=duration_minutes)
    return start, end


@pytest.fixture(scope="session")
def integration_settings() -> dict[str, str]:
    """Point the application to a dedicated MongoDB test database."""
    db_name = os.environ.get("TEST_MONGODB_DB_NAME", DEFAULT_TEST_DB_NAME)
    mongodb_uri = os.environ.get("TEST_MONGODB_URI", DEFAULT_TEST_MONGODB_URI)
    if db_name in UNSAFE_DATABASE_NAMES:
        raise RuntimeError(
            "Refusing to run integration tests against the development database "
            f"'{db_name}'. Use a dedicated test database instead."
        )

    env_updates = {
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "MONGODB_URI": mongodb_uri,
        "MONGODB_DB_NAME": db_name,
        "JWT_SECRET_KEY": "integration-test-secret",
        "ADMIN_EMAILS": f'["{ADMIN_EMAIL}"]',
    }
    original_values = {key: os.environ.get(key) for key in env_updates}

    try:
        mongo_client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=2000)
        mongo_client.admin.command("ping")
        topology = mongo_client.admin.command("hello")
        if not topology.get("setName"):
            pytest.skip(
                "MongoDB replica set support is required for transactional integration tests. "
                "Start the local single-node replica set first."
            )
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"MongoDB is required for integration tests: {exc}")

    mongo_client.drop_database(db_name)
    for key, value in env_updates.items():
        os.environ[key] = value
    get_settings.cache_clear()

    yield {
        "mongodb_uri": mongodb_uri,
        "db_name": db_name,
    }

    mongo_client.drop_database(db_name)
    mongo_client.close()
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def app(integration_settings: dict[str, str]) -> AsyncIterator[object]:
    """Create a FastAPI app instance connected to the dedicated test database."""
    _ = integration_settings
    get_settings.cache_clear()

    from app.main import create_application

    application = create_application()
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture(autouse=True)
async def clean_database(app: object) -> AsyncIterator[None]:
    """Clear all domain collections before and after each integration test."""
    _ = app
    from app.db.database import mongodb_manager

    database = mongodb_manager.get_database()
    collections = (
        DatabaseCollections.ORDERS,
        DatabaseCollections.TICKETS,
        DatabaseCollections.SESSIONS,
        DatabaseCollections.MOVIES,
        DatabaseCollections.USERS,
    )
    for collection_name in collections:
        await database[collection_name].delete_many({})

    yield

    for collection_name in collections:
        await database[collection_name].delete_many({})


@pytest_asyncio.fixture
async def client(app: object) -> AsyncIterator[httpx.AsyncClient]:
    """Create an async HTTP client bound to the FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def database(app: object, integration_settings: dict[str, str]):
    """Expose the active Motor database for state assertions."""
    _ = app
    from app.db.database import mongodb_manager

    database = mongodb_manager.get_database()
    assert database.name == integration_settings["db_name"]
    return database


@pytest.fixture
def auth_headers() -> Callable[[str], dict[str, str]]:
    """Build a bearer token header."""

    def _build(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _build


@pytest_asyncio.fixture
async def register_user(
    client: httpx.AsyncClient,
) -> Callable[..., Awaitable[httpx.Response]]:
    """Register a user through the API."""

    async def _register(
        *,
        email: str,
        name: str = "Cinema User",
        password: str = DEFAULT_PASSWORD,
    ) -> httpx.Response:
        return await client.post(
            f"{API_PREFIX}/auth/register",
            json={
                "email": email,
                "name": name,
                "password": password,
            },
        )

    return _register


@pytest_asyncio.fixture
async def login_user(
    client: httpx.AsyncClient,
) -> Callable[..., Awaitable[httpx.Response]]:
    """Authenticate a user through the API."""

    async def _login(*, email: str, password: str = DEFAULT_PASSWORD) -> httpx.Response:
        return await client.post(
            f"{API_PREFIX}/auth/login",
            data={
                "username": email,
                "password": password,
            },
        )

    return _login


@pytest_asyncio.fixture
async def create_authenticated_user(
    register_user: Callable[..., Awaitable[httpx.Response]],
    login_user: Callable[..., Awaitable[httpx.Response]],
    auth_headers: Callable[[str], dict[str, str]],
) -> Callable[..., Awaitable[dict[str, object]]]:
    """Create and log in a user through the API."""

    async def _create(
        *,
        email: str,
        name: str,
        password: str = DEFAULT_PASSWORD,
    ) -> dict[str, object]:
        register_response = await register_user(email=email, name=name, password=password)
        assert register_response.status_code == 201, register_response.text

        login_response = await login_user(email=email, password=password)
        assert login_response.status_code == 200, login_response.text

        token = login_response.json()["data"]["access_token"]
        return {
            "token": token,
            "headers": auth_headers(token),
            "user": register_response.json()["data"],
            "password": password,
        }

    return _create


@pytest_asyncio.fixture
async def admin_auth(create_authenticated_user: Callable[..., Awaitable[dict[str, object]]]) -> dict[str, object]:
    """Create an authenticated admin user."""
    return await create_authenticated_user(email=ADMIN_EMAIL, name="Admin User")


@pytest_asyncio.fixture
async def user_auth(create_authenticated_user: Callable[..., Awaitable[dict[str, object]]]) -> dict[str, object]:
    """Create an authenticated regular user."""
    return await create_authenticated_user(email=USER_EMAIL, name="Regular User")


@pytest_asyncio.fixture
async def create_movie(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
) -> Callable[..., Awaitable[dict[str, object]]]:
    """Create a movie through the admin API."""

    async def _create(
        *,
        title: str = "Interstellar",
        description: str = "Science fiction epic",
        duration_minutes: int = 169,
        genres: list[str] | None = None,
        status: str = "planned",
    ) -> dict[str, object]:
        response = await client.post(
            f"{API_PREFIX}/admin/movies",
            headers=admin_auth["headers"],
            json={
                "title": build_localized_text(title),
                "description": build_localized_text(description),
                "duration_minutes": duration_minutes,
                "poster_url": None,
                "age_rating": "PG-13",
                "genres": genres or ["science_fiction", "drama"],
                "status": status,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]

    return _create


@pytest_asyncio.fixture
async def create_session(
    client: httpx.AsyncClient,
    admin_auth: dict[str, object],
) -> Callable[..., Awaitable[dict[str, object]]]:
    """Create a session through the admin API."""

    async def _create(
        *,
        movie_id: str,
        day_offset: int = 1,
        start_hour: int = 10,
        duration_minutes: int = 180,
        price: float = 200,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, object]:
        computed_start, computed_end = build_session_window(
            day_offset=day_offset,
            start_hour=start_hour,
            duration_minutes=duration_minutes,
        )
        response = await client.post(
            f"{API_PREFIX}/admin/sessions",
            headers=admin_auth["headers"],
            json={
                "movie_id": movie_id,
                "start_time": (start_time or computed_start).isoformat(),
                "end_time": (end_time or computed_end).isoformat(),
                "price": price,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["data"]

    return _create
