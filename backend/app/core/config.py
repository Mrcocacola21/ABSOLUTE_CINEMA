"""Application settings powered by Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed runtime configuration for the backend."""

    project_name: str = "Cinema Showcase API"
    project_version: str = "0.2.0"
    project_description: str = (
        "Academic starter backend for a one-hall cinema schedule and ticketing system."
    )
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "cinema_showcase"
    jwt_secret_key: str = "<CHANGE_ME>"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    log_level: str = "INFO"
    cinema_timezone: str = "Europe/Kyiv"
    hall_rows_count: int = 8
    hall_seats_per_row: int = 12
    first_session_hour: int = 9
    last_session_start_hour: int = 22
    admin_emails: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_value(cls, value: object) -> object:
        """Accept a few non-boolean environment conventions for debug mode."""
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False
        return value

    @property
    def total_seats(self) -> int:
        """Return the fixed seat count for the single hall."""
        return self.hall_rows_count * self.hall_seats_per_row


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance to behave like a singleton."""
    return Settings()
