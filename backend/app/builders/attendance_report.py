"""Builder for attendance report responses."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.report import AttendanceReportRead, AttendanceSessionSummary


class AttendanceReportBuilder:
    """Incrementally assemble attendance report payloads."""

    def __init__(self) -> None:
        self._generated_at = datetime.now(tz=timezone.utc)
        self._sessions: list[AttendanceSessionSummary] = []
        self._total_tickets_sold = 0
        self._total_checked_in_tickets = 0
        self._total_unchecked_active_tickets = 0
        self._total_cancelled_tickets = 0

    def add_session(self, session_summary: AttendanceSessionSummary) -> "AttendanceReportBuilder":
        """Append a session attendance summary to the report."""
        self._sessions.append(session_summary)
        self._total_tickets_sold += session_summary.tickets_sold
        self._total_checked_in_tickets += session_summary.checked_in_tickets_count
        self._total_unchecked_active_tickets += session_summary.unchecked_active_tickets_count
        self._total_cancelled_tickets += session_summary.cancelled_tickets_count
        return self

    def build(self) -> AttendanceReportRead:
        """Finalize the attendance report DTO."""
        return AttendanceReportRead(
            generated_at=self._generated_at,
            total_sessions=len(self._sessions),
            total_tickets_sold=self._total_tickets_sold,
            total_checked_in_tickets=self._total_checked_in_tickets,
            total_unchecked_active_tickets=self._total_unchecked_active_tickets,
            total_cancelled_tickets=self._total_cancelled_tickets,
            sessions=self._sessions,
        )
