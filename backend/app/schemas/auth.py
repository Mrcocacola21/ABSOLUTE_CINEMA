"""Authentication-related schemas."""

from pydantic import BaseModel, EmailStr


class TokenRead(BaseModel):
    """Response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str
    email: EmailStr
    role: str
    exp: int
