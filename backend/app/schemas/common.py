"""Common reusable Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Shared base model configuration for all schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="ignore",
        str_strip_whitespace=True,
    )


class PaginationParams(BaseSchema):
    """Pagination input parameters."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginationMeta(BaseSchema):
    """Pagination metadata returned in successful list responses."""

    total: int
    limit: int
    offset: int
    current_page: int
    total_pages: int


class DeleteResultRead(BaseSchema):
    """Standard payload returned by delete operations."""

    id: str
    deleted: bool = True
