"""Route-level regressions for admin order validation."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.api.dependencies.auth import get_current_admin
from app.api.dependencies.services import get_order_service
from app.core.constants import Roles
from app.main import create_application
from app.schemas.order import OrderValidationRead
from app.schemas.user import UserRead


def build_admin_user() -> UserRead:
    now = datetime.now(tz=timezone.utc)
    return UserRead(
        id="admin-1",
        name="Admin",
        email="admin@example.com",
        role=Roles.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=None,
    )


class FakeOrderValidationService:
    def __init__(self) -> None:
        self.validated_tokens: list[tuple[str, str]] = []

    async def validate_order_token(self, token: str, requested_by: UserRead) -> OrderValidationRead:
        self.validated_tokens.append((token, requested_by.id))
        return OrderValidationRead(
            scanned_at=datetime.now(tz=timezone.utc),
            token_status="valid_token",
            order_id="order-1",
            is_valid_for_entry=True,
            validity_code="valid",
            message="The order has unchecked active tickets for a future scheduled session.",
            can_check_in=True,
            order_status="completed",
            movie_title={"uk": "Movie", "en": "Movie"},
            active_tickets_count=1,
            unchecked_active_tickets_count=1,
        )


@pytest.mark.asyncio
async def test_admin_validate_order_token_route_returns_current_validation_shape() -> None:
    app = create_application()
    service = FakeOrderValidationService()
    app.dependency_overrides[get_current_admin] = build_admin_user
    app.dependency_overrides[get_order_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/admin/orders/validate/demo-token")

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert service.validated_tokens == [("demo-token", "admin-1")]
    assert payload["token_status"] == "valid_token"
    assert payload["validity_code"] == "valid"
    assert payload["can_check_in"] is True
    assert "entry_status_code" not in payload
    assert "entry_status_message" not in payload
