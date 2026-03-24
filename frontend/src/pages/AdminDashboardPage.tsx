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
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { AttendanceReport, Movie, Session, SessionDetails, TicketListItem, User } from "@/types/domain";
import { AttendancePanel } from "@/widgets/admin/AttendancePanel";
import { AdminScheduleManagement } from "@/widgets/admin/AdminScheduleManagement";

export function AdminDashboardPage() {
  const { t } = useTranslation();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [sessions, setSessions] = useState<SessionDetails[]>([]);
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [report, setReport] = useState<AttendanceReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [pendingActionLabel, setPendingActionLabel] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error";
    title: string;
    message: string;
  } | null>(null);

  async function refreshDashboard(options?: { background?: boolean }) {
    const background = options?.background ?? false;
    if (background) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }

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
      const message = extractApiErrorMessage(error, "Admin data is currently unavailable.");
      if (background) {
        setFeedback({
          tone: "error",
          title: "Unable to refresh dashboard data",
          message,
        });
      } else {
        setErrorMessage(message);
      }
    } finally {
      if (background) {
        setIsRefreshing(false);
      } else {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void refreshDashboard();
  }, []);

  async function runAdminAction<T>(
    action: () => Promise<{ message: string; data: T }>,
    actionLabel: string,
    successTitle: string,
    fallbackMessage: string,
  ): Promise<T | null> {
    setPendingActionLabel(actionLabel);
    setFeedback(null);
    try {
      const response = await action();
      await refreshDashboard({ background: true });
      setFeedback({
        tone: "success",
        title: successTitle,
        message: response.message,
      });
      return response.data;
    } catch (error) {
      setFeedback({
        tone: "error",
        title: `${successTitle} failed`,
        message: extractApiErrorMessage(error, fallbackMessage),
      });
      return null;
    } finally {
      setPendingActionLabel("");
    }
  }

  async function handleCreateMovie(payload: MovieCreatePayload) {
    return runAdminAction(
      () => createMovieRequest(payload),
      "Creating movie",
      "Movie created",
      "Movie creation failed.",
    );
  }

  async function handleUpdateMovie(movieId: string, payload: MovieUpdatePayload) {
    return runAdminAction(
      () => updateMovieRequest(movieId, payload),
      "Updating movie",
      "Movie updated",
      "Movie update failed.",
    );
  }

  async function handleDeactivateMovie(movieId: string) {
    return runAdminAction(
      () => deactivateMovieRequest(movieId),
      "Deactivating movie",
      "Movie deactivated",
      "Movie deactivation failed.",
    );
  }

  async function handleDeleteMovie(movieId: string) {
    return runAdminAction(
      () => deleteMovieRequest(movieId),
      "Deleting movie",
      "Movie deleted",
      "Movie deletion failed.",
    );
  }

  async function handleCreateSession(payload: SessionCreatePayload) {
    return runAdminAction(
      () => createSessionRequest(payload),
      "Creating session",
      "Session created",
      "Session creation failed.",
    );
  }

  async function handleUpdateSession(sessionId: string, payload: SessionUpdatePayload) {
    return runAdminAction(
      () => updateSessionRequest(sessionId, payload),
      "Updating session",
      "Session updated",
      "Session update failed.",
    );
  }

  async function handleCancelSession(sessionId: string) {
    return runAdminAction(
      () => cancelSessionRequest(sessionId),
      "Cancelling session",
      "Session cancelled",
      "Session cancellation failed.",
    );
  }

  async function handleDeleteSession(sessionId: string) {
    return runAdminAction(
      () => deleteSessionRequest(sessionId),
      "Deleting session",
      "Session deleted",
      "Session deletion failed.",
    );
  }

  const activeMoviesCount = movies.filter((movie) => movie.is_active).length;
  const scheduledSessionsCount = sessions.filter((session) => session.status === "scheduled").length;

  return (
    <>
      <section className="page-header">
        <div>
          <p className="page-eyebrow">{t("adminWorkspaceEyebrow")}</p>
          <h1 className="page-title">{t("dashboard")}</h1>
          <p className="page-subtitle">{t("adminIntro")}</p>
        </div>
        <div className="actions-row">
          <span className="badge">
            {activeMoviesCount}/{movies.length} {t("movieCatalogTitle")}
          </span>
          <span className="badge">
            {scheduledSessionsCount}/{sessions.length} {t("sessionBoardTitle")}
          </span>
          <span className="badge">
            {tickets.length} {t("ticketsPanelTitle")}
          </span>
          <span className="badge">
            {users.length} {t("usersPanelTitle")}
          </span>
          <button
            className="button--ghost"
            type="button"
            disabled={isLoading || isRefreshing || Boolean(pendingActionLabel)}
            onClick={() => void refreshDashboard({ background: true })}
          >
            {isRefreshing ? "Refreshing..." : "Refresh data"}
          </button>
        </div>
      </section>

      <section className="cards-grid admin-overview-grid">
        <article className="card admin-overview-card">
          <p className="page-eyebrow">Movie Management</p>
          <h2 className="section-title">Maintain the catalog</h2>
          <p className="muted">
            Create titles, update metadata, and keep the active lineup ready for scheduling.
          </p>
          <div className="stats-row">
            <span className="badge">{activeMoviesCount} active</span>
            <span className="badge">{movies.length - activeMoviesCount} archived</span>
          </div>
        </article>
        <article className="card admin-overview-card">
          <p className="page-eyebrow">Session Planner</p>
          <h2 className="section-title">Schedule on the chronoboard</h2>
          <p className="muted">
            Drag an active movie onto the board, confirm the slot, and manage the day view in one lane.
          </p>
          <div className="stats-row">
            <span className="badge">{scheduledSessionsCount} scheduled</span>
            <span className="badge">{sessions.length - scheduledSessionsCount} closed out</span>
          </div>
        </article>
        <article className="card admin-overview-card">
          <p className="page-eyebrow">Reports</p>
          <h2 className="section-title">Track demand and attendance</h2>
          <p className="muted">
            Review attendance, latest bookings, and new users without leaving the admin workspace.
          </p>
          <div className="stats-row">
            <span className="badge">{tickets.length} bookings</span>
            <span className="badge">{users.length} accounts</span>
          </div>
        </article>
      </section>

      {pendingActionLabel || isRefreshing ? (
        <StatusBanner
          tone="info"
          title="Refreshing dashboard"
          message={pendingActionLabel ? `${pendingActionLabel}...` : "Refreshing the latest dashboard data."}
        />
      ) : null}

      {feedback ? (
        <StatusBanner
          tone={feedback.tone}
          title={feedback.title}
          message={feedback.message}
        />
      ) : null}

      {isLoading ? (
        <StatePanel
          tone="loading"
          title="Loading the admin dashboard"
          message="Fetching movies, sessions, tickets, users, and attendance."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title="Unable to load the admin dashboard"
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void refreshDashboard()}>
              Try again
            </button>
          }
        />
      ) : null}

      {!isLoading && !errorMessage ? (
        <>
          <AdminScheduleManagement
            movies={movies}
            sessions={sessions}
            isBusy={Boolean(pendingActionLabel)}
            busyActionLabel={pendingActionLabel}
            onCreateMovie={handleCreateMovie}
            onUpdateMovie={handleUpdateMovie}
            onDeactivateMovie={handleDeactivateMovie}
            onDeleteMovie={handleDeleteMovie}
            onCreateSession={handleCreateSession}
            onUpdateSession={handleUpdateSession}
            onCancelSession={handleCancelSession}
            onDeleteSession={handleDeleteSession}
          />
          <AttendancePanel report={report} tickets={tickets} users={users} />
        </>
      ) : null}
    </>
  );
}
