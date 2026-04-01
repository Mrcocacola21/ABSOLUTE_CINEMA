"""Attendance report schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.localization import LocalizedText


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
