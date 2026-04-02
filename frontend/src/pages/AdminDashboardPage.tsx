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
import { isMovieActive } from "@/shared/movieStatus";
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
      const message = extractApiErrorMessage(error, t("admin.dashboard.unavailableMessage"));
      if (background) {
        setFeedback({
          tone: "error",
          title: t("admin.dashboard.refreshErrorTitle"),
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
    options: {
      pendingKey: string;
      successTitleKey: string;
      successMessageKey: string;
      errorTitleKey: string;
      fallbackMessageKey: string;
    },
  ): Promise<T | null> {
    setPendingActionLabel(t(options.pendingKey));
    setFeedback(null);
    try {
      const response = await action();
      await refreshDashboard({ background: true });
      setFeedback({
        tone: "success",
        title: t(options.successTitleKey),
        message: t(options.successMessageKey),
      });
      return response.data;
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t(options.errorTitleKey),
        message: extractApiErrorMessage(error, t(options.fallbackMessageKey)),
      });
      return null;
    } finally {
      setPendingActionLabel("");
    }
  }

  async function handleCreateMovie(payload: MovieCreatePayload) {
    return runAdminAction(
      () => createMovieRequest(payload),
      {
        pendingKey: "admin.actions.createMovieLoading",
        successTitleKey: "admin.actions.createMovieSuccessTitle",
        successMessageKey: "admin.actions.createMovieSuccessMessage",
        errorTitleKey: "admin.actions.createMovieErrorTitle",
        fallbackMessageKey: "admin.actions.createMovieFailure",
      },
    );
  }

  async function handleUpdateMovie(movieId: string, payload: MovieUpdatePayload) {
    return runAdminAction(
      () => updateMovieRequest(movieId, payload),
      {
        pendingKey: "admin.actions.updateMovieLoading",
        successTitleKey: "admin.actions.updateMovieSuccessTitle",
        successMessageKey: "admin.actions.updateMovieSuccessMessage",
        errorTitleKey: "admin.actions.updateMovieErrorTitle",
        fallbackMessageKey: "admin.actions.updateMovieFailure",
      },
    );
  }

  async function handleDeactivateMovie(movieId: string) {
    return runAdminAction(
      () => deactivateMovieRequest(movieId),
      {
        pendingKey: "admin.actions.deactivateMovieLoading",
        successTitleKey: "admin.actions.deactivateMovieSuccessTitle",
        successMessageKey: "admin.actions.deactivateMovieSuccessMessage",
        errorTitleKey: "admin.actions.deactivateMovieErrorTitle",
        fallbackMessageKey: "admin.actions.deactivateMovieFailure",
      },
    );
  }

  async function handleDeleteMovie(movieId: string) {
    return runAdminAction(
      () => deleteMovieRequest(movieId),
      {
        pendingKey: "admin.actions.deleteMovieLoading",
        successTitleKey: "admin.actions.deleteMovieSuccessTitle",
        successMessageKey: "admin.actions.deleteMovieSuccessMessage",
        errorTitleKey: "admin.actions.deleteMovieErrorTitle",
        fallbackMessageKey: "admin.actions.deleteMovieFailure",
      },
    );
  }

  async function handleCreateSession(payload: SessionCreatePayload) {
    return runAdminAction(
      () => createSessionRequest(payload),
      {
        pendingKey: "admin.actions.createSessionLoading",
        successTitleKey: "admin.actions.createSessionSuccessTitle",
        successMessageKey: "admin.actions.createSessionSuccessMessage",
        errorTitleKey: "admin.actions.createSessionErrorTitle",
        fallbackMessageKey: "admin.actions.createSessionFailure",
      },
    );
  }

  async function handleUpdateSession(sessionId: string, payload: SessionUpdatePayload) {
    return runAdminAction(
      () => updateSessionRequest(sessionId, payload),
      {
        pendingKey: "admin.actions.updateSessionLoading",
        successTitleKey: "admin.actions.updateSessionSuccessTitle",
        successMessageKey: "admin.actions.updateSessionSuccessMessage",
        errorTitleKey: "admin.actions.updateSessionErrorTitle",
        fallbackMessageKey: "admin.actions.updateSessionFailure",
      },
    );
  }

  async function handleCancelSession(sessionId: string) {
    return runAdminAction(
      () => cancelSessionRequest(sessionId),
      {
        pendingKey: "admin.actions.cancelSessionLoading",
        successTitleKey: "admin.actions.cancelSessionSuccessTitle",
        successMessageKey: "admin.actions.cancelSessionSuccessMessage",
        errorTitleKey: "admin.actions.cancelSessionErrorTitle",
        fallbackMessageKey: "admin.actions.cancelSessionFailure",
      },
    );
  }

  async function handleDeleteSession(sessionId: string) {
    return runAdminAction(
      () => deleteSessionRequest(sessionId),
      {
        pendingKey: "admin.actions.deleteSessionLoading",
        successTitleKey: "admin.actions.deleteSessionSuccessTitle",
        successMessageKey: "admin.actions.deleteSessionSuccessMessage",
        errorTitleKey: "admin.actions.deleteSessionErrorTitle",
        fallbackMessageKey: "admin.actions.deleteSessionFailure",
      },
    );
  }

  const activeMoviesCount = movies.filter((movie) => isMovieActive(movie)).length;
  const plannedMoviesCount = movies.filter((movie) => movie.status === "planned").length;
  const deactivatedMoviesCount = movies.filter((movie) => movie.status === "deactivated").length;
  const scheduledSessionsCount = sessions.filter((session) => session.status === "scheduled").length;

  return (
    <>
      <section className="page-header">
        <div>
          <p className="page-eyebrow">{t("admin.dashboard.eyebrow")}</p>
          <h1 className="page-title">{t("admin.dashboard.title")}</h1>
          <p className="page-subtitle">{t("admin.dashboard.intro")}</p>
        </div>
        <div className="actions-row">
          <span className="badge">
            {activeMoviesCount} {t("common.states.active")}
          </span>
          <span className="badge">
            {plannedMoviesCount} {t("common.states.planned")}
          </span>
          <span className="badge">
            {deactivatedMoviesCount} {t("common.states.deactivated")}
          </span>
          <span className="badge">
            {scheduledSessionsCount}/{sessions.length} {t("common.labels.sessions")}
          </span>
          <span className="badge">
            {tickets.length} {t("common.labels.tickets")}
          </span>
          <span className="badge">
            {users.length} {t("common.labels.users")}
          </span>
          <button
            className="button--ghost"
            type="button"
            disabled={isLoading || isRefreshing || Boolean(pendingActionLabel)}
            onClick={() => void refreshDashboard({ background: true })}
          >
            {isRefreshing ? t("common.actions.refresh") : t("common.actions.refreshData")}
          </button>
        </div>
      </section>

      <section className="cards-grid admin-overview-grid">
        <article className="card admin-overview-card">
          <p className="page-eyebrow">{t("admin.overview.movieManagementEyebrow")}</p>
          <h2 className="section-title">{t("admin.overview.movieManagementTitle")}</h2>
          <p className="muted">{t("admin.overview.movieManagementText")}</p>
          <div className="stats-row">
            <span className="badge">{plannedMoviesCount} {t("common.states.planned")}</span>
            <span className="badge">{activeMoviesCount} {t("common.states.active")}</span>
            <span className="badge">{deactivatedMoviesCount} {t("common.states.deactivated")}</span>
          </div>
        </article>
        <article className="card admin-overview-card">
          <p className="page-eyebrow">{t("admin.overview.sessionPlannerEyebrow")}</p>
          <h2 className="section-title">{t("admin.overview.sessionPlannerTitle")}</h2>
          <p className="muted">{t("admin.overview.sessionPlannerText")}</p>
          <div className="stats-row">
            <span className="badge">{scheduledSessionsCount} {t("admin.overview.scheduled")}</span>
            <span className="badge">{sessions.length - scheduledSessionsCount} {t("admin.overview.closedOut")}</span>
          </div>
        </article>
        <article className="card admin-overview-card">
          <p className="page-eyebrow">{t("admin.overview.reportsEyebrow")}</p>
          <h2 className="section-title">{t("admin.overview.reportsTitle")}</h2>
          <p className="muted">{t("admin.overview.reportsText")}</p>
          <div className="stats-row">
            <span className="badge">{tickets.length} {t("common.stats.bookings")}</span>
            <span className="badge">{users.length} {t("common.stats.accounts")}</span>
          </div>
        </article>
      </section>

      {pendingActionLabel || isRefreshing ? (
        <StatusBanner
          tone="info"
          title={t("admin.dashboard.refreshBannerTitle")}
          message={pendingActionLabel ? `${pendingActionLabel}...` : t("admin.dashboard.refreshBannerMessage")}
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
          title={t("admin.dashboard.loadingTitle")}
          message={t("admin.dashboard.loadingMessage")}
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <StatePanel
          tone="error"
          title={t("admin.dashboard.errorTitle")}
          message={errorMessage}
          action={
            <button className="button--ghost" type="button" onClick={() => void refreshDashboard()}>
              {t("common.actions.retry")}
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
