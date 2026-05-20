"""Unit tests for authenticated user service behavior."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.constants import Roles
from app.core.exceptions import NotFoundException, ValidationException
from app.schemas.user import UserRead, UserUpdate
from app.security.hashing import password_hasher
from app.services.user import UserService

DEFAULT_PASSWORD = "CinemaPass123"
DEFAULT_PASSWORD_HASH = password_hasher.hash_password(DEFAULT_PASSWORD)


class FakeUserRepository:
    """In-memory user repository double for service tests."""

    def __init__(self, users: list[dict[str, object]]) -> None:
        self.users = {str(user["id"]): dict(user) for user in users}
        self.update_calls: list[dict[str, object]] = []

    async def get_by_id(self, user_id: str) -> dict[str, object] | None:
        user = self.users.get(user_id)
        return dict(user) if user is not None else None

    async def update_user(
        self,
        user_id: str,
        *,
        updates: dict[str, object],
        updated_at: datetime,
    ) -> dict[str, object] | None:
        self.update_calls.append(
            {
                "user_id": user_id,
                "updates": updates,
                "updated_at": updated_at,
            }
        )
        if user_id not in self.users:
            return None
        self.users[user_id] = {
            **self.users[user_id],
            **updates,
            "updated_at": updated_at,
        }
        return dict(self.users[user_id])

    async def list_users(self) -> list[dict[str, object]]:
        return [dict(user) for user in self.users.values()]


def build_user_document(
    user_id: str = "user-1",
    *,
    name: str = "Cinema User",
    email: str = "user@example.com",
    password: str = DEFAULT_PASSWORD,
    role: str = Roles.USER,
    is_active: bool = True,
) -> dict[str, object]:
    now = datetime.now(tz=timezone.utc)
    return {
        "id": user_id,
        "name": name,
        "email": email,
        "password_hash": DEFAULT_PASSWORD_HASH if password == DEFAULT_PASSWORD else password_hasher.hash_password(password),
        "role": role,
        "is_active": is_active,
        "created_at": now,
        "updated_at": None,
    }


def build_current_user(user_id: str = "user-1") -> UserRead:
    now = datetime.now(tz=timezone.utc)
    return UserRead(
        id=user_id,
        name="Cinema User",
        email="user@example.com",
        role=Roles.USER,
        is_active=True,
        created_at=now,
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_get_user_by_id_removes_password_hash_and_normalizes_unknown_role() -> None:
    service = UserService(
        FakeUserRepository(
            [
                build_user_document(role="unexpected-role"),
            ]
        )
    )

    user = await service.get_user_by_id("user-1")

    assert user is not None
    assert user.role == Roles.USER
    assert not hasattr(user, "password_hash")


@pytest.mark.asyncio
async def test_get_user_by_id_returns_none_for_missing_user() -> None:
    service = UserService(FakeUserRepository([]))

    assert await service.get_user_by_id("missing-user") is None


@pytest.mark.asyncio
async def test_update_current_user_updates_changed_name_without_password_check() -> None:
    repository = FakeUserRepository([build_user_document(name="Old Name")])
    service = UserService(repository)

    updated = await service.update_current_user(
        build_current_user(),
        UserUpdate(name="  New   Name  "),
    )

    assert updated.name == "New Name"
    assert repository.update_calls[0]["updates"] == {"name": "New Name"}


@pytest.mark.asyncio
async def test_update_current_user_requires_at_least_one_field() -> None:
    service = UserService(FakeUserRepository([build_user_document()]))

    with pytest.raises(ValidationException, match="At least one profile field"):
        await service.update_current_user(build_current_user(), UserUpdate())


@pytest.mark.asyncio
async def test_update_current_user_rejects_unchanged_profile_fields() -> None:
    service = UserService(FakeUserRepository([build_user_document(name="Cinema User")]))

    with pytest.raises(ValidationException, match="At least one changed profile field"):
        await service.update_current_user(build_current_user(), UserUpdate(name="Cinema User"))


@pytest.mark.asyncio
async def test_update_current_user_rejects_wrong_current_password_for_sensitive_changes() -> None:
    service = UserService(FakeUserRepository([build_user_document()]))

    with pytest.raises(ValidationException, match="Current password is incorrect."):
        await service.update_current_user(
            build_current_user(),
            UserUpdate(email="new@example.com", current_password="WrongPass123"),
        )


@pytest.mark.asyncio
async def test_update_current_user_changes_email_and_password_after_current_password_check() -> None:
    repository = FakeUserRepository([build_user_document(email="old@example.com")])
    service = UserService(repository)

    updated = await service.update_current_user(
        build_current_user(),
        UserUpdate(
            email="NEW@EXAMPLE.COM",
            password="BetterCinemaPass123",
            current_password="CinemaPass123",
        ),
    )

    updates = repository.update_calls[0]["updates"]
    assert updated.email == "new@example.com"
    assert updates["email"] == "new@example.com"
    assert "password_hash" in updates
    assert password_hasher.verify_password("BetterCinemaPass123", str(updates["password_hash"]))


@pytest.mark.asyncio
async def test_update_current_user_rejects_password_matching_existing_hash() -> None:
    repository = FakeUserRepository([build_user_document()])
    service = UserService(repository)
    payload = UserUpdate.model_construct(
        name=None,
        email=None,
        password="CinemaPass123",
        current_password="CinemaPass123",
    )

    with pytest.raises(ValidationException, match="New password must be different"):
        await service.update_current_user(build_current_user(), payload)


@pytest.mark.asyncio
async def test_update_current_user_reports_missing_user_before_update() -> None:
    service = UserService(FakeUserRepository([]))

    with pytest.raises(NotFoundException, match="User was not found."):
        await service.update_current_user(build_current_user(), UserUpdate(name="New Name"))


@pytest.mark.asyncio
async def test_deactivate_current_user_soft_deactivates_account() -> None:
    repository = FakeUserRepository([build_user_document()])
    service = UserService(repository)

    deactivated = await service.deactivate_current_user(build_current_user())

    assert deactivated.is_active is False
    assert repository.update_calls[0]["updates"] == {"is_active": False}


@pytest.mark.asyncio
async def test_deactivate_current_user_reports_missing_user() -> None:
    service = UserService(FakeUserRepository([]))

    with pytest.raises(NotFoundException, match="User was not found."):
        await service.deactivate_current_user(build_current_user())


@pytest.mark.asyncio
async def test_list_users_returns_profiles_without_sensitive_fields() -> None:
    service = UserService(
        FakeUserRepository(
            [
                build_user_document("admin-1", email="admin@example.com", role=Roles.ADMIN),
                build_user_document("user-1", email="user@example.com", role="legacy"),
            ]
        )
    )

    users = await service.list_users(build_current_user("admin-1"))

    assert [user.email for user in users] == ["admin@example.com", "user@example.com"]
    assert [user.role for user in users] == [Roles.ADMIN, Roles.USER]
