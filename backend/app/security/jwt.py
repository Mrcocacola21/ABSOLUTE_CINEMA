"""JWT token helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationException

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class BaseTokenPayload(BaseModel):
    """Common JWT payload shared by access and refresh tokens."""

    sub: str
    email: str
    role: str
    token_type: str
    exp: int
    iat: int
    jti: str


class AccessTokenPayload(BaseTokenPayload):
    """JWT payload used by the application access token."""

    token_type: Literal["access"]


class RefreshTokenPayload(BaseTokenPayload):
    """JWT payload used by the application refresh token."""

    token_type: Literal["refresh"]


def _create_token(
    *,
    subject: str,
    email: str,
    role: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
) -> tuple[str, int]:
    """Create a signed JWT and return it with its expiration in seconds."""
    settings = get_settings()
    issued_at = datetime.now(tz=timezone.utc)
    expires_at = issued_at + expires_delta
    payload = {
        "sub": subject,
        "email": email,
        "role": role,
        "token_type": token_type,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def create_access_token(subject: str, email: str, role: str) -> tuple[str, int]:
    """Create a signed JWT access token and return it with its expiration in seconds."""
    settings = get_settings()
    return _create_token(
        subject=subject,
        email=email,
        role=role,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str, email: str, role: str) -> tuple[str, int]:
    """Create a signed JWT refresh token and return it with its expiration in seconds."""
    settings = get_settings()
    return _create_token(
        subject=subject,
        email=email,
        role=role,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
    )


def _decode_token(
    token: str,
    *,
    payload_model: type[AccessTokenPayload] | type[RefreshTokenPayload],
    error_message: str,
) -> AccessTokenPayload | RefreshTokenPayload:
    """Decode and validate a token against the expected payload model."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload_model.model_validate(payload)
    except (JWTError, ValidationError) as exc:
        raise AuthenticationException(error_message) from exc


def decode_access_token(token: str) -> AccessTokenPayload:
    """Decode and validate an incoming JWT access token."""
    return _decode_token(
        token,
        payload_model=AccessTokenPayload,
        error_message="Invalid or expired access token.",
    )


def decode_refresh_token(token: str) -> RefreshTokenPayload:
    """Decode and validate an incoming JWT refresh token."""
    return _decode_token(
        token,
        payload_model=RefreshTokenPayload,
        error_message="Invalid or expired refresh token.",
    )
