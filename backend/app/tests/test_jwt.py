"""Unit tests for JWT helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationException
from app.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def test_create_access_token_and_decode_round_trip_expected_claims() -> None:
    token, expires_in = create_access_token(
        subject="507f1f77bcf86cd799439011",
        email="user@example.com",
        role="user",
    )

    payload = decode_access_token(token)

    assert expires_in > 0
    assert payload.sub == "507f1f77bcf86cd799439011"
    assert payload.email == "user@example.com"
    assert payload.role == "user"
    assert payload.token_type == "access"
    assert payload.exp > int(datetime.now(tz=timezone.utc).timestamp())
    assert payload.iat <= payload.exp
    assert payload.jti


def test_decode_access_token_rejects_expired_token() -> None:
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": "507f1f77bcf86cd799439011",
            "email": "user@example.com",
            "role": "user",
            "token_type": "access",
            "iat": int((datetime.now(tz=timezone.utc) - timedelta(minutes=10)).timestamp()),
            "exp": int((datetime.now(tz=timezone.utc) - timedelta(minutes=5)).timestamp()),
            "jti": "expired-access-token",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AuthenticationException, match="Invalid or expired access token."):
        decode_access_token(expired_token)


def test_create_refresh_token_and_decode_round_trip_expected_claims() -> None:
    token, expires_in = create_refresh_token(
        subject="507f1f77bcf86cd799439011",
        email="user@example.com",
        role="user",
    )

    payload = decode_refresh_token(token)

    assert expires_in > 0
    assert payload.sub == "507f1f77bcf86cd799439011"
    assert payload.email == "user@example.com"
    assert payload.role == "user"
    assert payload.token_type == "refresh"
    assert payload.exp > int(datetime.now(tz=timezone.utc).timestamp())
    assert payload.iat <= payload.exp
    assert payload.jti


def test_decode_refresh_token_rejects_access_token() -> None:
    token, _ = create_access_token(
        subject="507f1f77bcf86cd799439011",
        email="user@example.com",
        role="user",
    )

    with pytest.raises(AuthenticationException, match="Invalid or expired refresh token."):
        decode_refresh_token(token)
