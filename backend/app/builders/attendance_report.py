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

    def add_session(self, session_summary: AttendanceSessionSummary) -> "AttendanceReportBuilder":
        """Append a session attendance summary to the report."""
        self._sessions.append(session_summary)
        self._total_tickets_sold += session_summary.tickets_sold
        return self

    def build(self) -> AttendanceReportRead:
        """Finalize the attendance report DTO."""
        return AttendanceReportRead(
            generated_at=self._generated_at,
            total_sessions=len(self._sessions),
            total_tickets_sold=self._total_tickets_sold,
            sessions=self._sessions,
        )
