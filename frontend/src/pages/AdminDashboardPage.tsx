import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  cancelSessionRequest,
  createMovieRequest,
  createSessionRequest,
  deactivateMovieRequest,
  deleteMovieRequest,
  deleteSessionRequest,
  getAttendanceRequest,
  listAdminMoviesRequest,
  listAdminSessionsRequest,
  listAdminTicketsRequest,
  listAdminUsersRequest,
  type MovieCreatePayload,
  type MovieUpdatePayload,
  type SessionCreatePayload,
  type SessionUpdatePayload,
  updateMovieRequest,
  updateSessionRequest,
} from "@/api/admin";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import type { AttendanceReport, Movie, SessionDetails, TicketListItem, User } from "@/types/domain";
import { AttendancePanel } from "@/widgets/admin/AttendancePanel";
import { AdminScheduleManagement } from "@/widgets/admin/AdminScheduleManagement";

export function AdminDashboardPage() {
  const { t } = useTranslation();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [sessions, setSessions] = useState<SessionDetails[]>([]);
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [report, setReport] = useState<AttendanceReport | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  async function refreshDashboard() {
    try {
      const [moviesResponse, sessionsResponse, ticketsResponse, usersResponse, attendanceResponse] =
        await Promise.all([
          listAdminMoviesRequest(),
          listAdminSessionsRequest(),
          listAdminTicketsRequest(),
          listAdminUsersRequest(),
          getAttendanceRequest(),
        ]);

      setMovies(moviesResponse.data);
      setSessions(sessionsResponse.data);
      setTickets(ticketsResponse.data);
      setUsers(usersResponse.data);
      setReport(attendanceResponse.data);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, t("attendanceUnavailable")));
    }
  }

  useEffect(() => {
    void refreshDashboard();
  }, []);

  async function runAdminAction(
    action: () => Promise<{ message: string }>,
    fallbackMessage: string,
  ) {
    try {
      const response = await action();
      setStatusMessage(response.message);
      setErrorMessage("");
      await refreshDashboard();
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error, fallbackMessage));
    }
  }

  async function handleCreateMovie(payload: MovieCreatePayload) {
    await runAdminAction(() => createMovieRequest(payload), "Movie creation failed.");
  }

  async function handleUpdateMovie(movieId: string, payload: MovieUpdatePayload) {
    await runAdminAction(() => updateMovieRequest(movieId, payload), "Movie update failed.");
  }

  async function handleDeactivateMovie(movieId: string) {
    await runAdminAction(() => deactivateMovieRequest(movieId), "Movie deactivation failed.");
  }

  async function handleDeleteMovie(movieId: string) {
    await runAdminAction(() => deleteMovieRequest(movieId), "Movie deletion failed.");
  }

  async function handleCreateSession(payload: SessionCreatePayload) {
    await runAdminAction(() => createSessionRequest(payload), "Session creation failed.");
  }

  async function handleUpdateSession(sessionId: string, payload: SessionUpdatePayload) {
    await runAdminAction(() => updateSessionRequest(sessionId, payload), "Session update failed.");
  }

  async function handleCancelSession(sessionId: string) {
    await runAdminAction(() => cancelSessionRequest(sessionId), "Session cancellation failed.");
  }

  async function handleDeleteSession(sessionId: string) {
    await runAdminAction(() => deleteSessionRequest(sessionId), "Session deletion failed.");
  }

  return (
    <>
      <section className="panel">
        <h1 className="page-title">{t("dashboard")}</h1>
        <p className="muted">{t("adminIntro")}</p>
        {statusMessage ? <p className="badge">{statusMessage}</p> : null}
        {errorMessage ? <p className="badge badge--danger">{errorMessage}</p> : null}
      </section>
      <AdminScheduleManagement
        movies={movies}
        sessions={sessions}
        tickets={tickets}
        users={users}
        onCreateMovie={handleCreateMovie}
        onUpdateMovie={handleUpdateMovie}
        onDeactivateMovie={handleDeactivateMovie}
        onDeleteMovie={handleDeleteMovie}
        onCreateSession={handleCreateSession}
        onUpdateSession={handleUpdateSession}
        onCancelSession={handleCancelSession}
        onDeleteSession={handleDeleteSession}
      />
      <AttendancePanel report={report} />
    </>
  );
}
