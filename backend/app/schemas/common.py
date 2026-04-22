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

    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of items returned in one page.")
    offset: int = Field(default=0, ge=0, description="Zero-based number of items skipped before the current page.")


class PaginationMeta(BaseSchema):
    """Pagination metadata returned in successful list responses."""

    total: int = Field(description="Total number of matching items available.")
    limit: int = Field(description="Page size used for the current response.")
    offset: int = Field(description="Zero-based item offset used for the current response.")
    current_page: int = Field(description="Human-friendly current page number starting from 1.")
    total_pages: int = Field(description="Total number of available pages.")


class DeleteResultRead(BaseSchema):
    """Standard payload returned by delete operations."""

    id: str = Field(description="Identifier of the deleted resource.")
    deleted: bool = Field(default=True, description="Always `true` when the delete operation succeeded.")
