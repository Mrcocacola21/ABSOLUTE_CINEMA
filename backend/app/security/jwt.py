"""JWT token helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.exceptions import AuthenticationException


class AccessTokenPayload(BaseModel):
    """JWT payload used by the application access token."""

    sub: str
    email: str
    role: str
    exp: int


def create_access_token(subject: str, email: str, role: str) -> tuple[str, int]:
    """Create a signed JWT access token and return it with its expiration in seconds."""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_at = datetime.now(tz=timezone.utc) + expires_delta
    payload = {
        "sub": subject,
        "email": email,
        "role": role,
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> AccessTokenPayload:
    """Decode and validate an incoming JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return AccessTokenPayload.model_validate(payload)
    except (JWTError, ValidationError) as exc:
        raise AuthenticationException("Invalid or expired access token.") from exc
