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

    session_id: str = Field(description="Session identifier.")
    movie_title: LocalizedText = Field(description="Localized movie title for the reported session.")
    start_time: datetime = Field(description="Session start time.")
    status: str = Field(description="Current session lifecycle status.")
    tickets_sold: int = Field(ge=0, description="Active purchased tickets currently occupying seats.")
    checked_in_tickets_count: int = Field(
        default=0,
        ge=0,
        description="Active purchased tickets already checked in by staff.",
    )
    unchecked_active_tickets_count: int = Field(
        default=0,
        ge=0,
        description="Active purchased tickets that have not been checked in yet.",
    )
    cancelled_tickets_count: int = Field(
        default=0,
        ge=0,
        description="Cancelled tickets linked to this session; these seats are available again.",
    )
    total_seats: int = Field(ge=0, description="Total configured seats in the hall.")
    available_seats: int = Field(ge=0, description="Derived available seats after active purchased tickets.")
    attendance_rate: float = Field(ge=0, description="Active sold seats divided by total seats.")


class AttendanceReportRead(BaseSchema):
    """Attendance report returned to administrators."""

    generated_at: datetime = Field(description="Timestamp when the report was generated.")
    total_sessions: int = Field(ge=0, description="Number of sessions included in the report.")
    total_tickets_sold: int = Field(ge=0, description="Total active purchased tickets across reported sessions.")
    total_checked_in_tickets: int = Field(
        default=0,
        ge=0,
        description="Total active purchased tickets already checked in across reported sessions.",
    )
    total_unchecked_active_tickets: int = Field(
        default=0,
        ge=0,
        description="Total active purchased tickets not yet checked in across reported sessions.",
    )
    total_cancelled_tickets: int = Field(
        default=0,
        ge=0,
        description="Total cancelled tickets across reported sessions.",
    )
    sessions: list[AttendanceSessionSummary] = Field(description="Per-session attendance summaries.")


class AttendanceTicketDetailsRead(TicketRead):
    """Occupied ticket data enriched for admin attendance details."""

    user_name: str | None = Field(default=None, description="Ticket owner's display name, when available.")
    user_email: EmailStr | None = Field(default=None, description="Ticket owner's email, when available.")
    order_status: str | None = Field(default=None, description="Current status of the grouped order, when available.")


class AttendanceSessionDetailsRead(BaseSchema):
    """Detailed attendance payload for one session."""

    generated_at: datetime = Field(description="Timestamp when the detail report was generated.")
    session: SessionDetailsRead = Field(description="Session details with nested movie metadata.")
    seat_map: SessionSeatsRead = Field(description="Seat availability map built from active purchased tickets.")
    tickets_sold: int = Field(ge=0, description="Active purchased tickets currently occupying seats.")
    checked_in_tickets_count: int = Field(
        default=0,
        ge=0,
        description="Active purchased tickets already checked in by staff.",
    )
    unchecked_active_tickets_count: int = Field(
        default=0,
        ge=0,
        description="Active purchased tickets that have not been checked in yet.",
    )
    cancelled_tickets_count: int = Field(
        default=0,
        ge=0,
        description="Cancelled tickets linked to this session.",
    )
    attendance_rate: float = Field(ge=0, description="Active sold seats divided by total seats.")
    occupied_tickets: list[AttendanceTicketDetailsRead] = Field(
        description="Active purchased tickets that currently occupy seats.",
    )
    cancelled_tickets: list[AttendanceTicketDetailsRead] = Field(
        default_factory=list,
        description="Cancelled tickets for audit/reporting context; their seats are not occupied.",
    )
