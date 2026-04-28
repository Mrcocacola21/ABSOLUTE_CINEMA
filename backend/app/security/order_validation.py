"""Signed order validation token helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

ORDER_VALIDATION_TOKEN_TYPE = "order_validation"


class OrderValidationTokenPayload(BaseModel):
    """Payload stored in QR validation tokens."""

    sub: str
    typ: str
    iat: int


def create_order_validation_token(order_id: str) -> str:
    """Create a signed, non-expiring token that identifies one order."""
    settings = get_settings()
    payload = {
        "sub": order_id,
        "typ": ORDER_VALIDATION_TOKEN_TYPE,
        "iat": int(datetime.now(tz=timezone.utc).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_order_validation_token(token: str) -> OrderValidationTokenPayload | None:
    """Decode an order validation token, returning None when it is not trusted."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        parsed = OrderValidationTokenPayload.model_validate(payload)
    except (JWTError, ValidationError):
        return None

    if parsed.typ != ORDER_VALIDATION_TOKEN_TYPE:
        return None
    return parsed
