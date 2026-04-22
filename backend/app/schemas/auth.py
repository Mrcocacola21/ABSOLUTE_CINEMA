"""Authentication-related schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TokenRead(BaseModel):
    """Response returned after successful authentication."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.demo.signature",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        }
    )

    access_token: str = Field(
        description="Signed JWT bearer token used for authenticated API requests.",
    )
    token_type: str = Field(
        default="bearer",
        description="OAuth2 token type. The API uses bearer tokens.",
        json_schema_extra={"enum": ["bearer"]},
    )
    expires_in: int = Field(
        description="Token lifetime in seconds from the moment the access token was issued.",
        ge=1,
    )


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str = Field(description="User identifier stored in the token subject claim.")
    email: EmailStr = Field(description="Authenticated user email embedded in the token.")
    role: str = Field(
        description="Authenticated user role embedded in the token.",
        json_schema_extra={"enum": ["user", "admin"]},
    )
    exp: int = Field(description="JWT expiration timestamp as a Unix epoch value.")
