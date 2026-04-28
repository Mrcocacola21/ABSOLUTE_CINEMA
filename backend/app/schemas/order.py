"""Order-related schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field, model_validator

from app.core.constants import ORDER_STATUS_VALUES, TicketStatuses
from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText

TICKET_STATUS_VALUES = (TicketStatuses.PURCHASED, TicketStatuses.CANCELLED)


class OrderSeatInput(BaseSchema):
    """One seat included in an order purchase request."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    seat_row: int = Field(
        ge=1,
        description="One-based seat row inside the configured one-hall layout.",
    )
    seat_number: int = Field(
        ge=1,
        description="One-based seat number inside the selected row.",
    )


class OrderPurchaseRequest(BaseSchema):
    """Payload for purchasing multiple seats for one session."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "session_id": "6803a522e5d4c4d94e7e1a10",
                "seats": [
                    {"seat_row": 4, "seat_number": 5},
                    {"seat_row": 4, "seat_number": 6},
                ],
            }
        },
    )

    session_id: str = Field(description="Identifier of the scheduled session being purchased.")
    seats: list[OrderSeatInput] = Field(
        min_length=1,
        description="Unique seat coordinates to purchase in one grouped order.",
    )

    @model_validator(mode="after")
    def validate_unique_seats(self) -> "OrderPurchaseRequest":
        """Reject duplicate seat coordinates inside the same request."""
        unique_seats = {(seat.seat_row, seat.seat_number) for seat in self.seats}
        if len(unique_seats) != len(self.seats):
            raise ValueError("Each seat may only appear once in the purchase request.")
        return self


class OrderRead(BaseSchema):
    """Order DTO returned by the API."""

    id: str
    user_id: str
    session_id: str
    status: str
    total_price: float = Field(ge=0)
    tickets_count: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "OrderRead":
        """Restrict order status values to the supported lifecycle states."""
        if self.status not in ORDER_STATUS_VALUES:
            raise ValueError("Unsupported order status.")
        return self


class OrderTicketRead(BaseSchema):
    """Ticket data embedded inside order responses."""

    id: str
    order_id: str | None = None
    seat_row: int = Field(ge=1)
    seat_number: int = Field(ge=1)
    price: float = Field(gt=0)
    status: str
    purchased_at: datetime
    updated_at: datetime | None = None
    cancelled_at: datetime | None = None
    is_cancellable: bool

    @model_validator(mode="after")
    def validate_ticket_state(self) -> "OrderTicketRead":
        """Keep nested order tickets aligned with supported ticket lifecycle values."""
        if self.status not in TICKET_STATUS_VALUES:
            raise ValueError("Unsupported ticket status.")
        if self.status == TicketStatuses.CANCELLED and self.cancelled_at is None:
            raise ValueError("Cancelled tickets must include cancelled_at.")
        if self.status == TicketStatuses.PURCHASED and self.cancelled_at is not None:
            raise ValueError("Purchased tickets cannot include cancelled_at.")
        return self


class OrderListRead(OrderRead):
    """Order DTO enriched with session, movie, and nested ticket data."""

    movie_id: str
    movie_title: LocalizedText
    poster_url: str | None = None
    age_rating: str | None = None
    session_start_time: datetime
    session_end_time: datetime
    session_status: str
    active_tickets_count: int = Field(ge=0)
    cancelled_tickets_count: int = Field(ge=0)
    tickets: list[OrderTicketRead]


class OrderDetailsRead(OrderListRead):
    """Dedicated schema for order details responses."""
