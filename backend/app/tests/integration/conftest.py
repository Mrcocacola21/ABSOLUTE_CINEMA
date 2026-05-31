"""Shared fixtures for backend integration tests."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timedelta
import hashlib
import hmac
import json
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
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


def _integration_mongodb_required() -> bool:
    return os.environ.get("REQUIRE_INTEGRATION_MONGODB", "").strip().lower() in TRUTHY_ENV_VALUES


def _unavailable_integration_mongodb(message: str) -> None:
    if _integration_mongodb_required():
        raise RuntimeError(message)
    pytest.skip(message)


def build_localized_text(value: str, *, en: str | None = None) -> dict[str, str]:
    """Build a localized text payload for tests."""
    return {
        "uk": value,
        "en": en or value,
    }


def build_default_test_ukrainian_text(value: str, *, prefix: str) -> str:
    """Generate deterministic Ukrainian placeholder text for English-led test fixtures."""
    normalized = value.strip()
    if not normalized:
        return prefix

    checksum = sum(ord(character) for character in normalized if not character.isspace())
    return f"{prefix} {checksum}"


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


def sign_fake_webhook_payload(payload: dict[str, object]) -> tuple[bytes, str]:
    """Build a signed fake-provider webhook body for integration tests."""
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(b"fake-webhook-secret", raw_body, hashlib.sha256).hexdigest()
    return raw_body, signature


async def complete_reserved_order_payment(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    order_id: str,
) -> dict[str, object]:
    """Initiate payment and process a successful fake-provider webhook for one reserved order."""
    initiation_response = await client.post(
        f"{API_PREFIX}/orders/{order_id}/payments",
        headers=headers,
        json={"metadata": {"source": "integration_test_completion"}},
    )
    assert initiation_response.status_code == 201, initiation_response.text
    initiation = initiation_response.json()["data"]

    raw_body, signature = sign_fake_webhook_payload(
        {
            "event_id": f"evt-integration-paid-{order_id}",
            "event_type": "payment.updated",
            "occurred_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
            "payment": {
                "id": initiation["provider_payment_id"],
                "status": "paid",
                "amount_minor": initiation["amount_minor"],
                "currency": initiation["currency"],
            },
        }
    )
    webhook_response = await client.post(
        f"{API_PREFIX}/payments/webhook",
        headers={"x-fake-payment-signature": signature},
        content=raw_body,
    )
    assert webhook_response.status_code == 200, webhook_response.text
    assert webhook_response.json()["data"]["processing_status"] == "processed"
    return initiation


async def purchase_order_and_complete(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    session_id: str,
    seats: list[dict[str, int]],
) -> dict[str, object]:
    """Reserve seats, complete fake-provider payment, and return refreshed order details."""
    response = await client.post(
        f"{API_PREFIX}/orders/purchase",
        headers=headers,
        json={
            "session_id": session_id,
            "seats": seats,
        },
    )
    assert response.status_code == 201, response.text
    order = response.json()["data"]
    await complete_reserved_order_payment(client, headers, order["id"])

    detail_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{order['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    return detail_response.json()["data"]


async def purchase_ticket_and_complete(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    session_id: str,
    seat_row: int,
    seat_number: int,
) -> dict[str, object]:
    """Reserve one ticket through the legacy wrapper, complete payment, and return the refreshed ticket."""
    response = await client.post(
        f"{API_PREFIX}/tickets/purchase",
        headers=headers,
        json={
            "session_id": session_id,
            "seat_row": seat_row,
            "seat_number": seat_number,
        },
    )
    assert response.status_code == 201, response.text
    reserved_ticket = response.json()["data"]
    await complete_reserved_order_payment(client, headers, reserved_ticket["order_id"])

    detail_response = await client.get(
        f"{API_PREFIX}/users/me/orders/{reserved_ticket['order_id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    tickets = detail_response.json()["data"]["tickets"]
    return next(ticket for ticket in tickets if ticket["id"] == reserved_ticket["id"])


@pytest.fixture(scope="session")
def integration_settings() -> dict[str, str]:
    """Point the application to a dedicated MongoDB test database."""
    db_name = os.environ.get("TEST_MONGODB_DB_NAME", DEFAULT_TEST_DB_NAME)
    mongodb_uri = os.environ.get("TEST_MONGODB_URI") or os.environ.get("MONGODB_URI") or DEFAULT_TEST_MONGODB_URI
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
    try:
        mongo_client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=2000)
        mongo_client.admin.command("ping")
        topology = mongo_client.admin.command("hello")
        if not topology.get("setName"):
            _unavailable_integration_mongodb(
                "MongoDB replica set support is required for transactional integration tests. "
                "Start the local single-node replica set first."
            )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - environment dependent
        _unavailable_integration_mongodb(f"MongoDB is required for integration tests: {exc}")

    media_root = tempfile.mkdtemp(prefix="cinema-test-media-")
    env_updates["MEDIA_ROOT"] = media_root
    original_values = {key: os.environ.get(key) for key in env_updates}

    mongo_client.drop_database(db_name)
    for key, value in env_updates.items():
        os.environ[key] = value
    get_settings.cache_clear()

    yield {
        "mongodb_uri": mongodb_uri,
        "db_name": db_name,
        "media_root": media_root,
    }

    mongo_client.drop_database(db_name)
    mongo_client.close()
    shutil.rmtree(media_root, ignore_errors=True)
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
        DatabaseCollections.PAYMENTS,
        DatabaseCollections.PAYMENT_ATTEMPTS,
        DatabaseCollections.PAYMENT_WEBHOOK_EVENTS,
        DatabaseCollections.PAYMENT_AUDIT_EVENTS,
        DatabaseCollections.REFUNDS,
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

        token_payload = login_response.json()["data"]
        token = token_payload["access_token"]
        return {
            "token": token,
            "refresh_token": token_payload["refresh_token"],
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
        title_uk: str | None = None,
        description: str = "Science fiction epic",
        description_uk: str | None = None,
        duration_minutes: int = 169,
        poster_url: str | None = None,
        genres: list[str] | None = None,
        status: str = "planned",
    ) -> dict[str, object]:
        response = await client.post(
            f"{API_PREFIX}/admin/movies",
            headers=admin_auth["headers"],
            json={
                "title": {
                    "uk": title_uk or build_default_test_ukrainian_text(title, prefix="Фільм"),
                    "en": title,
                },
                "description": {
                    "uk": description_uk or build_default_test_ukrainian_text(description, prefix="Опис"),
                    "en": description,
                },
                "duration_minutes": duration_minutes,
                "poster_url": poster_url,
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
