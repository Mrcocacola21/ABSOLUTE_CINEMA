"""Authentication-related schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AccessTokenRead(BaseModel):
    """Response containing a bearer access token."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.demo.signature",
                "token_type": "bearer",
                "expires_in": 900,
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


class TokenRead(AccessTokenRead):
    """Response returned after successful authentication."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.demo.signature",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh.signature",
                "token_type": "bearer",
                "expires_in": 900,
                "refresh_expires_in": 604800,
            }
        }
    )

    refresh_token: str = Field(
        description=(
            "Signed JWT refresh token used only with POST /api/v1/auth/refresh to obtain a new access token."
        ),
    )
    refresh_expires_in: int = Field(
        description="Refresh token lifetime in seconds from the moment it was issued.",
        ge=1,
    )


class TokenRefreshRequest(BaseModel):
    """Request body for refreshing an access token."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refresh.signature",
            }
        }
    )

    refresh_token: str = Field(
        min_length=1,
        description="Refresh JWT returned by the login or Swagger token endpoint.",
    )


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str = Field(description="User identifier stored in the token subject claim.")
    email: EmailStr = Field(description="Authenticated user email embedded in the token.")
    role: str = Field(
        description="Authenticated user role embedded in the token.",
        json_schema_extra={"enum": ["user", "admin"]},
    )
    token_type: str = Field(
        description="JWT purpose claim. Access tokens and refresh tokens are not interchangeable.",
        json_schema_extra={"enum": ["access", "refresh"]},
    )
    exp: int = Field(description="JWT expiration timestamp as a Unix epoch value.")
    iat: int = Field(description="JWT issued-at timestamp as a Unix epoch value.")
    jti: str = Field(description="Unique token identifier generated for each issued token.")
