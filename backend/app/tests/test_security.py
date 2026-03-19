"""Unit tests for password hashing utilities."""

from app.security.hashing import password_hasher


def test_password_hasher_hashes_and_verifies_password() -> None:
    password = "CinemaPass123"
    hashed_password = password_hasher.hash_password(password)

    assert hashed_password != password
    assert password_hasher.verify_password(password, hashed_password) is True
