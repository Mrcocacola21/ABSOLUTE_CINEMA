import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getIntlLocale, getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type {
  AttendanceReport,
  AttendanceSessionSummary,
  LocalizedText,
  TicketListItem,
  User,
} from "@/types/domain";

type AttendanceStatusFilter = "all" | "scheduled" | "completed" | "cancelled";
type AttendanceSortOption = "latest" | "highest" | "lowest";
type BookingSortOption = "latest" | "oldest";
type ReportTabId = "attendance" | "bookings" | "accounts";

interface ReportMetricCard {
  label: string;
  value: number | string;
  detail: string;
}

interface BookingSessionOption {
  sessionId: string;
  movieTitle: LocalizedText;
  startTime: string;
  status: string;
  ticketCount: number;
}

const attendanceStatusFilters: AttendanceStatusFilter[] = ["all", "scheduled", "completed", "cancelled"];
const attendanceSortOptions: AttendanceSortOption[] = ["latest", "highest", "lowest"];
const bookingSortOptions: BookingSortOption[] = ["latest", "oldest"];

interface AttendancePanelProps {
  report: AttendanceReport | null;
  tickets: TicketListItem[];
  users: User[];
  isLoading?: boolean;
  errorMessage?: string;
  onRetry?: () => void;
}

function formatPercent(value: number, language: string): string {
  return new Intl.NumberFormat(getIntlLocale(language), {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value);
}

function getAttendanceRowTone(session: AttendanceSessionSummary): string {
  if (session.status === "cancelled") {
    return "cancelled";
  }

  if (session.available_seats === 0 || session.attendance_rate >= 0.7) {
    return "strong";
  }

  if (session.attendance_rate <= 0.25) {
    return "weak";
  }

  return "balanced";
}

function getBookingSessionLabel(movieTitle: LocalizedText, startTime: string, language: string): string {
  return `${getLocalizedText(movieTitle, language)} | ${formatDateTime(startTime, language)}`;
}

function MetricGrid({
  cards,
  className,
}: {
  cards: ReportMetricCard[];
  className: string;
}) {
  return (
    <div className={className}>
      {cards.map((card) => (
        <article key={card.label} className="admin-report-mini-card">
          <span className="admin-report-mini-card__label">{card.label}</span>
          <strong>{card.value}</strong>
          <p className="muted">{card.detail}</p>
        </article>
      ))}
    </div>
  );
}

export function AttendancePanel({
  report,
  tickets,
  users,
  isLoading = false,
  errorMessage = "",
  onRetry,
}: AttendancePanelProps) {
  const { t, i18n } = useTranslation();
  const [statusFilter, setStatusFilter] = useState<AttendanceStatusFilter>("all");
  const [sortOption, setSortOption] = useState<AttendanceSortOption>("latest");
  const [activeTab, setActiveTab] = useState<ReportTabId>("attendance");
  const [bookingSessionFilter, setBookingSessionFilter] = useState("all");
  const [bookingSearchQuery, setBookingSearchQuery] = useState("");
  const [bookingSortOption, setBookingSortOption] = useState<BookingSortOption>("latest");

  const recentUsers = [...users]
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
    .slice(0, 6);
  const activeUsers = users.filter((user) => user.is_active).length;
  const inactiveUsers = users.length - activeUsers;

  const sessions = report?.sessions ?? [];
  const now = Date.now();
  const totalSeats = sessions.reduce((sum, session) => sum + session.total_seats, 0);
  const overallAttendanceRate = totalSeats > 0 ? (report?.total_tickets_sold ?? 0) / totalSeats : 0;
  const upcomingSessionsCount = sessions.filter(
    (session) => session.status === "scheduled" && new Date(session.start_time).getTime() >= now,
  ).length;
  const completedSessionsCount = sessions.filter((session) => session.status === "completed").length;
  const cancelledSessionsCount = sessions.filter((session) => session.status === "cancelled").length;
  const soldOutSessionsCount = sessions.filter(
    (session) => session.status !== "cancelled" && session.total_seats > 0 && session.available_seats === 0,
  ).length;

  const comparableSessions = sessions.filter((session) => session.status !== "cancelled");
  const bestSession =
    comparableSessions.length > 0
      ? [...comparableSessions].sort(
          (left, right) =>
            right.attendance_rate - left.attendance_rate ||
            new Date(right.start_time).getTime() - new Date(left.start_time).getTime(),
        )[0]
      : null;
  const weakestSession =
    comparableSessions.length > 1
      ? [...comparableSessions]
          .sort(
            (left, right) =>
              left.attendance_rate - right.attendance_rate ||
              new Date(right.start_time).getTime() - new Date(left.start_time).getTime(),
          )
          .find((session) => session.session_id !== bestSession?.session_id) ?? null
      : null;

  const filteredSessions = sessions.filter((session) => statusFilter === "all" || session.status === statusFilter);
  const visibleSessions = [...filteredSessions].sort((left, right) => {
    if (sortOption === "highest") {
      return (
        right.attendance_rate - left.attendance_rate ||
        new Date(right.start_time).getTime() - new Date(left.start_time).getTime()
      );
    }

    if (sortOption === "lowest") {
      return (
        left.attendance_rate - right.attendance_rate ||
        new Date(right.start_time).getTime() - new Date(left.start_time).getTime()
      );
    }

    return new Date(right.start_time).getTime() - new Date(left.start_time).getTime();
  });

  const bookingSessionsMap = new Map<string, BookingSessionOption>();

  for (const session of sessions) {
    bookingSessionsMap.set(session.session_id, {
      sessionId: session.session_id,
      movieTitle: session.movie_title,
      startTime: session.start_time,
      status: session.status,
      ticketCount: 0,
    });
  }

  for (const ticket of tickets) {
    const existing = bookingSessionsMap.get(ticket.session_id);
    if (existing) {
      existing.ticketCount += 1;
      continue;
    }

    bookingSessionsMap.set(ticket.session_id, {
      sessionId: ticket.session_id,
      movieTitle: ticket.movie_title,
      startTime: ticket.session_start_time,
      status: ticket.session_status,
      ticketCount: 1,
    });
  }

  const bookingSessionOptions = [...bookingSessionsMap.values()].sort(
    (left, right) => new Date(right.startTime).getTime() - new Date(left.startTime).getTime(),
  );
  const selectedBookingSession =
    bookingSessionFilter === "all"
      ? null
      : bookingSessionOptions.find((session) => session.sessionId === bookingSessionFilter) ?? null;
  const normalizedBookingSearchQuery = bookingSearchQuery.trim().toLowerCase();
  const filteredBookings = tickets.filter((ticket) => {
    if (bookingSessionFilter !== "all" && ticket.session_id !== bookingSessionFilter) {
      return false;
    }

    if (!normalizedBookingSearchQuery) {
      return true;
    }

    const sessionLabel = getBookingSessionLabel(ticket.movie_title, ticket.session_start_time, i18n.language);
    const searchableParts = [
      getLocalizedText(ticket.movie_title, i18n.language),
      sessionLabel,
      ticket.session_start_time,
      ticket.user_name ?? "",
      ticket.user_email ?? "",
      `${ticket.seat_row}-${ticket.seat_number}`,
    ];

    return searchableParts.join(" ").toLowerCase().includes(normalizedBookingSearchQuery);
  });

  const visibleBookings = [...filteredBookings].sort((left, right) => {
    if (bookingSortOption === "oldest") {
      return new Date(left.purchased_at).getTime() - new Date(right.purchased_at).getTime();
    }

    return new Date(right.purchased_at).getTime() - new Date(left.purchased_at).getTime();
  });
  const visibleBookingSessionsCount = new Set(visibleBookings.map((ticket) => ticket.session_id)).size;
  const visibleBookingBuyersCount = new Set(visibleBookings.map((ticket) => ticket.user_id)).size;

  const reportSummaryCards: ReportMetricCard[] = report
    ? [
        {
          label: t("admin.reports.summary.sessionsInReport"),
          value: report.total_sessions,
          detail: t("admin.reports.summary.sessionsDetail"),
        },
        {
          label: t("admin.reports.summary.ticketsSold"),
          value: report.total_tickets_sold,
          detail: t("admin.reports.summary.ticketsDetail"),
        },
        {
          label: t("admin.reports.summary.occupancyRate"),
          value: formatPercent(overallAttendanceRate, i18n.language),
          detail: t("admin.reports.summary.occupancyDetail", {
            sold: report.total_tickets_sold,
            total: totalSeats,
          }),
        },
        {
          label: t("admin.reports.summary.upcomingSessions"),
          value: upcomingSessionsCount,
          detail: t("admin.reports.summary.upcomingDetail"),
        },
      ]
    : [];

  const bookingSummaryCards: ReportMetricCard[] = [
    {
      label: t("admin.reports.bookings.summary.visibleTickets"),
      value: visibleBookings.length,
      detail: t("admin.reports.bookings.summary.visibleTicketsDetail"),
    },
    {
      label: t("admin.reports.bookings.summary.visibleSessions"),
      value: visibleBookingSessionsCount,
      detail: t("admin.reports.bookings.summary.visibleSessionsDetail"),
    },
    {
      label: t("admin.reports.bookings.summary.visibleBuyers"),
      value: visibleBookingBuyersCount,
      detail: t("admin.reports.bookings.summary.visibleBuyersDetail"),
    },
  ];

  const accountSummaryCards: ReportMetricCard[] = [
    {
      label: t("admin.reports.accounts.summary.totalUsers"),
      value: users.length,
      detail: t("admin.reports.accounts.summary.totalUsersDetail"),
    },
    {
      label: t("admin.reports.accounts.summary.activeAccounts"),
      value: activeUsers,
      detail: t("admin.reports.accounts.summary.activeAccountsDetail"),
    },
    {
      label: t("admin.reports.accounts.summary.inactiveAccounts"),
      value: inactiveUsers,
      detail: t("admin.reports.accounts.summary.inactiveAccountsDetail"),
    },
  ];

  const reportTabs: Array<{ id: ReportTabId; label: string; count: number }> = [
    {
      id: "attendance",
      label: t("admin.reports.tabs.attendance"),
      count: report?.total_sessions ?? 0,
    },
    {
      id: "bookings",
      label: t("admin.reports.tabs.bookings"),
      count: tickets.length,
    },
    {
      id: "accounts",
      label: t("admin.reports.tabs.accounts"),
      count: users.length,
    },
  ];

  function renderAttendanceTab() {
    if (!report && isLoading) {
      return (
        <StatePanel
          tone="loading"
          title={t("admin.reports.loadingTitle")}
          message={t("admin.reports.loadingMessage")}
        />
      );
    }

    if (!report && errorMessage) {
      return (
        <StatePanel
          tone="error"
          title={t("admin.reports.errorTitle")}
          message={errorMessage}
          action={
            onRetry ? (
              <button className="button--ghost" type="button" onClick={() => void onRetry()}>
                {t("common.actions.retry")}
              </button>
            ) : null
          }
        />
      );
    }

    if (!report) {
      return (
        <section className="card admin-report-panel admin-report-panel--attendance">
          <section className="empty-state empty-state--panel">
            <h2>{t("admin.reports.attendance.emptyTitle")}</h2>
            <p>{t("admin.reports.attendance.emptyText")}</p>
          </section>
        </section>
      );
    }

    return (
      <section className="card admin-report-panel admin-report-panel--attendance">
        <div className="admin-report-panel__header">
          <div className="admin-report-panel__copy">
            <p className="page-eyebrow">{t("admin.reports.attendance.eyebrow")}</p>
            <h3 className="section-title">{t("admin.reports.attendance.title")}</h3>
            <p className="muted">{t("admin.reports.attendance.intro")}</p>
          </div>
          <div className="admin-report-panel__header-meta">
            <span className="badge">
              {t("admin.reports.attendance.showingResults", {
                visible: visibleSessions.length,
                total: sessions.length,
              })}
            </span>
          </div>
        </div>

        <div className="admin-report-toolbar">
          <div className="admin-report-toolbar__group">
            <span className="admin-report-toolbar__label">{t("common.labels.status")}</span>
            <div className="admin-report-toggle-group">
              {attendanceStatusFilters.map((filter) => (
                <button
                  key={filter}
                  className={`admin-report-toggle ${statusFilter === filter ? "is-active" : ""}`}
                  type="button"
                  aria-pressed={statusFilter === filter}
                  onClick={() => setStatusFilter(filter)}
                >
                  {t(`admin.reports.attendance.filters.${filter}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="admin-report-toolbar__group">
            <span className="admin-report-toolbar__label">{t("common.labels.sortBy")}</span>
            <div className="admin-report-toggle-group">
              {attendanceSortOptions.map((option) => (
                <button
                  key={option}
                  className={`admin-report-toggle ${sortOption === option ? "is-active" : ""}`}
                  type="button"
                  aria-pressed={sortOption === option}
                  onClick={() => setSortOption(option)}
                >
                  {t(`admin.reports.attendance.sort.${option}`)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {sessions.length > 0 ? (
          <>
            <div className="admin-report-insights">
              {bestSession ? (
                <article className="admin-report-insight admin-report-insight--positive">
                  <span className="admin-report-insight__label">{t("admin.reports.attendance.bestAttendance")}</span>
                  <strong>{getLocalizedText(bestSession.movie_title, i18n.language)}</strong>
                  <p className="muted">{formatDateTime(bestSession.start_time, i18n.language)}</p>
                  <div className="stats-row">
                    <span className="badge badge--active">{t("admin.reports.attendance.bestBadge")}</span>
                    <span className="badge">{formatPercent(bestSession.attendance_rate, i18n.language)}</span>
                    <span className="badge">
                      {t("admin.reports.attendance.soldOfTotal", {
                        sold: bestSession.tickets_sold,
                        total: bestSession.total_seats,
                      })}
                    </span>
                  </div>
                </article>
              ) : null}

              {weakestSession ? (
                <article className="admin-report-insight admin-report-insight--warning">
                  <span className="admin-report-insight__label">
                    {t("admin.reports.attendance.weakestAttendance")}
                  </span>
                  <strong>{getLocalizedText(weakestSession.movie_title, i18n.language)}</strong>
                  <p className="muted">{formatDateTime(weakestSession.start_time, i18n.language)}</p>
                  <div className="stats-row">
                    <span className="badge badge--danger">{t("admin.reports.attendance.watchBadge")}</span>
                    <span className="badge">{formatPercent(weakestSession.attendance_rate, i18n.language)}</span>
                    <span className="badge">{formatStateLabel(weakestSession.status)}</span>
                  </div>
                </article>
              ) : null}

              <article className="admin-report-insight">
                <span className="admin-report-insight__label">{t("admin.reports.attendance.statusOverview")}</span>
                <strong>{t("admin.reports.attendance.upcomingOverview", { count: upcomingSessionsCount })}</strong>
                <p className="muted">{t("admin.reports.attendance.statusOverviewText")}</p>
                <div className="stats-row">
                  <span className="badge">{completedSessionsCount} {t("common.states.completed")}</span>
                  <span className="badge">{cancelledSessionsCount} {t("common.states.cancelled")}</span>
                  <span className="badge">{soldOutSessionsCount} {t("admin.reports.attendance.soldOutSessions")}</span>
                </div>
              </article>
            </div>

            {visibleSessions.length > 0 ? (
              <div className="admin-attendance-list">
                {visibleSessions.map((item) => {
                  const fillWidth = `${Math.max(0, Math.min(100, item.attendance_rate * 100))}%`;
                  const isBestSession = item.session_id === bestSession?.session_id;
                  const isWeakestSession = item.session_id === weakestSession?.session_id;

                  return (
                    <article
                      key={item.session_id}
                      className={`admin-attendance-row admin-attendance-row--${getAttendanceRowTone(item)}`}
                    >
                      <div className="admin-attendance-row__header">
                        <div className="admin-attendance-row__copy">
                          <strong>{getLocalizedText(item.movie_title, i18n.language)}</strong>
                          <p className="muted">{formatDateTime(item.start_time, i18n.language)}</p>
                        </div>
                        <div className="admin-attendance-row__tags">
                          {isBestSession ? (
                            <span className="badge badge--active">{t("admin.reports.attendance.bestBadge")}</span>
                          ) : null}
                          {isWeakestSession ? (
                            <span className="badge badge--danger">{t("admin.reports.attendance.watchBadge")}</span>
                          ) : null}
                          <span className="badge">{formatStateLabel(item.status)}</span>
                        </div>
                      </div>

                      <div className="admin-attendance-row__progress">
                        <div className="admin-attendance-row__progress-head">
                          <span>{t("admin.reports.attendance.fillRate")}</span>
                          <strong>{formatPercent(item.attendance_rate, i18n.language)}</strong>
                        </div>
                        <div className="admin-attendance-row__meter" aria-hidden="true">
                          <span style={{ width: fillWidth }} />
                        </div>
                        <p className="muted admin-attendance-row__progress-copy">
                          {t("admin.reports.attendance.soldOfTotal", {
                            sold: item.tickets_sold,
                            total: item.total_seats,
                          })}
                        </p>
                      </div>

                      <div className="admin-attendance-row__stats">
                        <div className="admin-attendance-row__stat">
                          <span>{t("common.labels.ticketsSold")}</span>
                          <strong>{item.tickets_sold}</strong>
                        </div>
                        <div className="admin-attendance-row__stat">
                          <span>{t("common.labels.availableSeats")}</span>
                          <strong>{item.available_seats}</strong>
                        </div>
                        <div className="admin-attendance-row__stat">
                          <span>{t("admin.reports.attendance.capacity")}</span>
                          <strong>{item.total_seats}</strong>
                        </div>
                      </div>

                      <div className="admin-attendance-row__footer">
                        <p className="muted">{t("admin.reports.attendance.detailsHint")}</p>
                        <Link className="button--ghost admin-attendance-row__action" to={`/admin/attendance/${item.session_id}`}>
                          {t("common.actions.viewDetails")}
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <section className="empty-state empty-state--panel">
                <h2>{t("admin.reports.attendance.filteredEmptyTitle")}</h2>
                <p>{t("admin.reports.attendance.filteredEmptyText")}</p>
                <button
                  className="button--ghost"
                  type="button"
                  onClick={() => {
                    setStatusFilter("all");
                    setSortOption("latest");
                  }}
                >
                  {t("common.actions.resetFilters")}
                </button>
              </section>
            )}
          </>
        ) : (
          <section className="empty-state empty-state--panel">
            <h2>{t("admin.reports.attendance.emptyTitle")}</h2>
            <p>{t("admin.reports.attendance.emptyText")}</p>
          </section>
        )}
      </section>
    );
  }

  function renderBookingsTab() {
    const bookingHelperText = selectedBookingSession
      ? t("admin.reports.bookings.selectedSessionHelper", {
          session: getBookingSessionLabel(
            selectedBookingSession.movieTitle,
            selectedBookingSession.startTime,
            i18n.language,
          ),
        })
      : t("admin.reports.bookings.allSessionsHelper");

    return (
      <section className="card admin-report-panel">
        <div className="admin-report-panel__header">
          <div className="admin-report-panel__copy">
            <p className="page-eyebrow">{t("admin.reports.bookings.eyebrow")}</p>
            <h3 className="section-title">{t("admin.reports.bookings.title")}</h3>
            <p className="muted">{t("admin.reports.bookings.intro")}</p>
          </div>
          <div className="admin-report-panel__header-meta">
            <span className="badge">{t("admin.reports.bookings.totalCount", { count: tickets.length })}</span>
            <span className="badge">{t("admin.reports.bookings.filteredCount", { count: visibleBookings.length })}</span>
          </div>
        </div>

        <section className="toolbar-panel admin-report-filter-panel">
          <div className="toolbar-panel__header">
            <div className="toolbar-panel__intro">
              <h4>{t("admin.reports.bookings.filterTitle")}</h4>
              <p className="toolbar-panel__summary">{bookingHelperText}</p>
            </div>
            <div className="toolbar-panel__results">
              <p className="toolbar-panel__results-value">
                {t("admin.reports.bookings.resultsSummary", {
                  count: visibleBookings.length,
                  sessions: visibleBookingSessionsCount,
                })}
              </p>
            </div>
          </div>

          <div className="admin-report-toolbar admin-report-toolbar--bookings">
            <label className="field field--search">
              <span>{t("admin.reports.bookings.filters.searchLabel")}</span>
              <input
                type="search"
                value={bookingSearchQuery}
                placeholder={t("admin.reports.bookings.filters.searchPlaceholder")}
                onChange={(event) => setBookingSearchQuery(event.target.value)}
              />
              <p className="field__hint">{t("admin.reports.bookings.queryHint")}</p>
            </label>

            <label className="field">
              <span>{t("admin.reports.bookings.filters.sessionLabel")}</span>
              <select
                value={bookingSessionFilter}
                onChange={(event) => setBookingSessionFilter(event.target.value)}
              >
                <option value="all">{t("admin.reports.bookings.filters.allSessions")}</option>
                {bookingSessionOptions.map((session) => (
                  <option key={session.sessionId} value={session.sessionId}>
                    {getBookingSessionLabel(session.movieTitle, session.startTime, i18n.language)}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>{t("admin.reports.bookings.filters.sortLabel")}</span>
              <select
                value={bookingSortOption}
                onChange={(event) => setBookingSortOption(event.target.value as BookingSortOption)}
              >
                {bookingSortOptions.map((option) => (
                  <option key={option} value={option}>
                    {t(`admin.reports.bookings.filters.sort.${option}`)}
                  </option>
                ))}
              </select>
            </label>

            <div className="toolbar__actions admin-report-toolbar__actions">
              <button
                className="button--ghost"
                type="button"
                onClick={() => {
                  setBookingSessionFilter("all");
                  setBookingSearchQuery("");
                  setBookingSortOption("latest");
                }}
              >
                {t("common.actions.resetFilters")}
              </button>
            </div>
          </div>
        </section>

        <MetricGrid cards={bookingSummaryCards} className="admin-report-mini-grid" />

        {tickets.length === 0 ? (
          <section className="empty-state empty-state--panel">
            <h2>{t("admin.reports.bookings.emptyTitle")}</h2>
            <p>{t("admin.reports.bookings.emptyText")}</p>
          </section>
        ) : visibleBookings.length > 0 ? (
          <div className="list admin-report-feed">
            {visibleBookings.map((ticket) => (
              <article key={ticket.id} className="admin-report-feed__item">
                <div className="admin-report-feed__top">
                  <div className="admin-report-feed__copy">
                    <strong>{getLocalizedText(ticket.movie_title, i18n.language)}</strong>
                    <p className="muted">
                      {formatDateTime(ticket.session_start_time, i18n.language)} |{" "}
                      {t("admin.reports.bookingSeat", { seat: `${ticket.seat_row}-${ticket.seat_number}` })}
                    </p>
                  </div>
                  <span className="badge">{formatCurrency(ticket.price, i18n.language)}</span>
                </div>

                <div className="admin-report-feed__buyer">
                  <strong>{ticket.user_name || t("admin.reports.bookings.buyerFallback")}</strong>
                  <span>{ticket.user_email || ticket.user_id}</span>
                </div>

                <div className="stats-row">
                  <span className="badge">{formatStateLabel(ticket.status)}</span>
                  <span className="badge">{formatStateLabel(ticket.session_status)}</span>
                  <span className="badge">
                    {t("admin.reports.bookings.purchasedLabel", {
                      date: formatDateTime(ticket.purchased_at, i18n.language),
                    })}
                  </span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <section className="empty-state empty-state--panel">
            <h2>{t("admin.reports.bookings.filteredEmptyTitle")}</h2>
            <p>{t("admin.reports.bookings.filteredEmptyText")}</p>
            <button
              className="button--ghost"
              type="button"
              onClick={() => {
                setBookingSessionFilter("all");
                setBookingSearchQuery("");
                setBookingSortOption("latest");
              }}
            >
              {t("common.actions.resetFilters")}
            </button>
          </section>
        )}
      </section>
    );
  }

  function renderAccountsTab() {
    return (
      <section className="card admin-report-panel">
        <div className="admin-report-panel__header">
          <div className="admin-report-panel__copy">
            <p className="page-eyebrow">{t("admin.reports.accounts.eyebrow")}</p>
            <h3 className="section-title">{t("admin.reports.accounts.title")}</h3>
            <p className="muted">{t("admin.reports.accounts.intro")}</p>
          </div>
          <div className="admin-report-panel__header-meta">
            <span className="badge">{t("admin.reports.accounts.latestCount", { count: recentUsers.length })}</span>
          </div>
        </div>

        <MetricGrid cards={accountSummaryCards} className="admin-report-mini-grid" />

        {recentUsers.length > 0 ? (
          <div className="list">
            {recentUsers.map((user) => (
              <article key={user.id} className="admin-report-feed__item">
                <div className="admin-report-feed__top">
                  <div className="admin-report-feed__copy">
                    <strong>{user.name}</strong>
                    <p className="muted">{user.email}</p>
                  </div>
                  <span className="badge">{formatDateTime(user.created_at, i18n.language)}</span>
                </div>
                <div className="stats-row">
                  <span className="badge">{formatStateLabel(user.role)}</span>
                  <span className="badge">
                    {user.is_active ? t("common.states.activeAccount") : t("common.states.inactiveAccount")}
                  </span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <section className="empty-state empty-state--panel">
            <h2>{t("admin.reports.accounts.emptyTitle")}</h2>
            <p>{t("admin.reports.accounts.emptyText")}</p>
          </section>
        )}
      </section>
    );
  }

  const attendanceTabId = "admin-report-tab-attendance";
  const bookingsTabId = "admin-report-tab-bookings";
  const accountsTabId = "admin-report-tab-accounts";

  return (
    <section className="panel admin-reports">
      <div className="admin-section__header">
        <div>
          <p className="page-eyebrow">{t("admin.reports.eyebrow")}</p>
          <h2 className="section-title">{t("admin.reports.title")}</h2>
          <p className="muted">{t("admin.reports.intro")}</p>
        </div>
        {report ? (
          <div className="admin-reports__meta">
            <span>{t("admin.reports.snapshotLabel")}</span>
            <strong>{formatDateTime(report.generated_at, i18n.language)}</strong>
          </div>
        ) : null}
      </div>

      {report && errorMessage ? (
        <StatusBanner
          tone="warning"
          title={t("admin.reports.staleTitle")}
          message={`${t("admin.reports.staleMessage")} ${errorMessage}`}
          action={
            onRetry ? (
              <button className="button--ghost" type="button" onClick={() => void onRetry()}>
                {t("common.actions.retry")}
              </button>
            ) : null
          }
        />
      ) : null}

      {!report && errorMessage && activeTab !== "attendance" ? (
        <StatusBanner
          tone="warning"
          title={t("admin.reports.errorTitle")}
          message={errorMessage}
          action={
            onRetry ? (
              <button className="button--ghost" type="button" onClick={() => void onRetry()}>
                {t("common.actions.retry")}
              </button>
            ) : null
          }
        />
      ) : null}

      {reportSummaryCards.length > 0 ? (
        <div className="cards-grid admin-report-summary">
          {reportSummaryCards.map((card) => (
            <article key={card.label} className="card admin-report-summary__card">
              <span className="admin-report-summary__eyebrow">{card.label}</span>
              <strong>{card.value}</strong>
              <p className="muted">{card.detail}</p>
            </article>
          ))}
        </div>
      ) : null}

      <div className="admin-report-tabs" role="tablist" aria-label={t("admin.reports.title")}>
        {reportTabs.map((tab) => {
          const isActive = tab.id === activeTab;
          const tabId =
            tab.id === "attendance"
              ? attendanceTabId
              : tab.id === "bookings"
                ? bookingsTabId
                : accountsTabId;

          return (
            <button
              key={tab.id}
              id={tabId}
              className={`admin-report-tab ${isActive ? "is-active" : ""}`}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`admin-report-panel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="admin-report-tab__label">{tab.label}</span>
              <span className="admin-report-tab__count">{tab.count}</span>
            </button>
          );
        })}
      </div>

      <div
        id={`admin-report-panel-${activeTab}`}
        className="admin-report-stage"
        role="tabpanel"
        aria-labelledby={
          activeTab === "attendance"
            ? attendanceTabId
            : activeTab === "bookings"
              ? bookingsTabId
              : accountsTabId
        }
      >
        {activeTab === "attendance" ? renderAttendanceTab() : null}
        {activeTab === "bookings" ? renderBookingsTab() : null}
        {activeTab === "accounts" ? renderAccountsTab() : null}
      </div>
    </section>
  );
}
