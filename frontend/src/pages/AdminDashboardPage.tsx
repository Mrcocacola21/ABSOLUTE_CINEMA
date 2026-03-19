import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  cancelSessionRequest,
  createMovieRequest,
  createSessionRequest,
  getAttendanceRequest,
  listAdminMoviesRequest,
  listAdminSessionsRequest,
  type MovieCreatePayload,
  type MovieUpdatePayload,
  type SessionCreatePayload,
  updateMovieRequest,
} from "@/api/admin";
import type { AttendanceReport, Movie, SessionDetails } from "@/types/domain";
import { AttendancePanel } from "@/widgets/admin/AttendancePanel";
import { AdminScheduleManagement } from "@/widgets/admin/AdminScheduleManagement";

export function AdminDashboardPage() {
  const { t } = useTranslation();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [sessions, setSessions] = useState<SessionDetails[]>([]);
  const [report, setReport] = useState<AttendanceReport | null>(null);
  const [statusMessage, setStatusMessage] = useState("");

  async function refreshDashboard() {
    try {
      const [moviesResponse, sessionsResponse, attendanceResponse] = await Promise.all([
        listAdminMoviesRequest(),
        listAdminSessionsRequest(),
        getAttendanceRequest(),
      ]);
      setMovies(moviesResponse.data);
      setSessions(sessionsResponse.data);
      setReport(attendanceResponse.data);
      setStatusMessage("");
    } catch {
      setStatusMessage(t("attendanceUnavailable"));
    }
  }

  useEffect(() => {
    void refreshDashboard();
  }, []);

  async function handleCreateMovie(payload: MovieCreatePayload) {
    await createMovieRequest(payload);
    setStatusMessage(t("movieCreatedMessage"));
    await refreshDashboard();
  }

  async function handleUpdateMovie(movieId: string, payload: MovieUpdatePayload) {
    await updateMovieRequest(movieId, payload);
    setStatusMessage(t("movieUpdatedMessage"));
    await refreshDashboard();
  }

  async function handleCreateSession(payload: SessionCreatePayload) {
    await createSessionRequest(payload);
    setStatusMessage(t("sessionCreatedMessage"));
    await refreshDashboard();
  }

  async function handleCancelSession(sessionId: string) {
    await cancelSessionRequest(sessionId);
    setStatusMessage(t("sessionCancelledMessage"));
    await refreshDashboard();
  }

  return (
    <>
      <section className="panel">
        <h1 className="page-title">{t("dashboard")}</h1>
        <p className="muted">{t("adminIntro")}</p>
        {statusMessage ? <p className="badge">{statusMessage}</p> : null}
      </section>
      <AdminScheduleManagement
        movies={movies}
        sessions={sessions}
        onCreateMovie={handleCreateMovie}
        onUpdateMovie={handleUpdateMovie}
        onCreateSession={handleCreateSession}
        onCancelSession={handleCancelSession}
      />
      <AttendancePanel report={report} />
    </>
  );
}
