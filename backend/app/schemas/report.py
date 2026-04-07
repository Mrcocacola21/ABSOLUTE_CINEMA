"""Attendance report schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText
from app.schemas.session import SessionDetailsRead, SessionSeatsRead
from app.schemas.ticket import TicketRead


class AttendanceSessionSummary(BaseSchema):
    """Summary of attendance metrics for a single session."""

    session_id: str
    movie_title: LocalizedText
    start_time: datetime
    status: str
    tickets_sold: int = Field(ge=0)
    total_seats: int = Field(ge=0)
    available_seats: int = Field(ge=0)
    attendance_rate: float = Field(ge=0)


class AttendanceReportRead(BaseSchema):
    """Attendance report returned to administrators."""

    generated_at: datetime
    total_sessions: int = Field(ge=0)
    total_tickets_sold: int = Field(ge=0)
    sessions: list[AttendanceSessionSummary]


class AttendanceTicketDetailsRead(TicketRead):
    """Occupied ticket data enriched for admin attendance details."""

    user_name: str | None = None
    user_email: EmailStr | None = None
    order_status: str | None = None


class AttendanceSessionDetailsRead(BaseSchema):
    """Detailed attendance payload for one session."""

    generated_at: datetime
    session: SessionDetailsRead
    seat_map: SessionSeatsRead
    tickets_sold: int = Field(ge=0)
    attendance_rate: float = Field(ge=0)
    occupied_tickets: list[AttendanceTicketDetailsRead]
