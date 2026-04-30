import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { getAttendanceSessionDetailsRequest } from "@/api/admin";
import { exportAttendanceSessionPdf } from "@/features/admin/attendancePdf";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getIntlLocale, getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatStateLabel, formatTime } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { AttendanceSessionDetails, AttendanceTicketDetails, SeatAvailability } from "@/types/domain";

type TicketSortOption = "seat" | "latest" | "oldest";

function buildSeatKey(row: number, seatNumber: number): string {
  return `${row}-${seatNumber}`;
}

function buildStatusToneClass(status?: string | null): string {
  if (!status) {
    return "admin-attendance-status-chip--neutral";
  }

  return `admin-attendance-status-chip--${status.replace(/_/g, "-")}`;
}

function isTicketCancelled(ticket: AttendanceTicketDetails): boolean {
  return ticket.status === "cancelled" || Boolean(ticket.cancelled_at);
}

function buildUsageToneClass(ticket: AttendanceTicketDetails): string {
  if (isTicketCancelled(ticket)) {
    return "admin-attendance-status-chip--cancelled";
  }

  return ticket.checked_in_at ? "admin-attendance-status-chip--used" : "admin-attendance-status-chip--not-used";
}

function formatPercent(value: number, language: string): string {
  return new Intl.NumberFormat(getIntlLocale(language), {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatLongDateTime(value: string, language: string): string {
  return new Intl.DateTimeFormat(getIntlLocale(language), {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatShortDate(value: string, language: string): string {
  return new Intl.DateTimeFormat(getIntlLocale(language), {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function groupSeats(seats: SeatAvailability[]): Array<{ row: number; seats: SeatAvailability[] }> {
  return [...seats]
    .sort((left, right) => {
      if (left.row === right.row) {
        return left.number - right.number;
      }

      return left.row - right.row;
    })
    .reduce<Array<{ row: number; seats: SeatAvailability[] }>>((rows, seat) => {
      const rowGroup = rows[rows.length - 1];

      if (!rowGroup || rowGroup.row !== seat.row) {
        rows.push({ row: seat.row, seats: [seat] });
        return rows;
      }

      rowGroup.seats.push(seat);
      return rows;
    }, []);
}

export function AdminAttendanceDetailsPage() {
  const { t, i18n } = useTranslation();
  const { sessionId = "" } = useParams();
  const [details, setDetails] = useState<AttendanceSessionDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isNotFound, setIsNotFound] = useState(false);
  const [selectedSeatKey, setSelectedSeatKey] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOption, setSortOption] = useState<TicketSortOption>("seat");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error" | "warning" | "info";
    title: string;
    message: string;
  } | null>(null);

  async function loadAttendanceDetails(options?: { background?: boolean }) {
    const background = options?.background ?? false;

    if (background) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
      setErrorMessage("");
      setIsNotFound(false);
    }

    try {
      const response = await getAttendanceSessionDetailsRequest(sessionId);
      const nextDetails = response.data;
      const occupiedSeatKeys = new Set(
        nextDetails.occupied_tickets.map((ticket) => buildSeatKey(ticket.seat_row, ticket.seat_number)),
      );

      setDetails(nextDetails);
      setSelectedSeatKey((current) => (current && occupiedSeatKeys.has(current) ? current : ""));
      setErrorMessage("");
      setIsNotFound(false);
    } catch (error) {
      const notFound = axios.isAxiosError(error) && error.response?.status === 404;
      const message = extractApiErrorMessage(error, t("admin.reports.attendanceDetail.errorMessage"));

      if (background) {
        setFeedback({
          tone: "error",
          title: t("admin.reports.attendanceDetail.refreshErrorTitle"),
          message,
        });
      } else {
        setDetails(null);
        setSelectedSeatKey("");
        setErrorMessage(message);
        setIsNotFound(notFound);
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
    setFeedback(null);
    void loadAttendanceDetails();
  }, [sessionId, t]);

  const groupedRows = useMemo(
    () => groupSeats(details?.seat_map.seats ?? []),
    [details?.seat_map.seats],
  );
  const occupiedSeatKeys = useMemo(
    () => new Set((details?.occupied_tickets ?? []).map((ticket) => buildSeatKey(ticket.seat_row, ticket.seat_number))),
    [details?.occupied_tickets],
  );
  const normalizedQuery = searchQuery.trim().toLowerCase();

  function isTicketReadyForEntry(ticket: AttendanceTicketDetails): boolean {
    return Boolean(
      details &&
        ticket.status === "purchased" &&
        ticket.order_status !== "cancelled" &&
        !ticket.checked_in_at &&
        !isTicketCancelled(ticket) &&
        details.session.status === "scheduled" &&
        new Date(details.session.start_time).getTime() > Date.now(),
    );
  }

  function getTicketUsageLabel(ticket: AttendanceTicketDetails): string {
    if (isTicketCancelled(ticket)) {
      return t("admin.reports.attendanceDetail.usage.cancelled");
    }

    return ticket.checked_in_at
      ? t("admin.reports.attendanceDetail.usage.used")
      : t("admin.reports.attendanceDetail.usage.notUsed");
  }

  function getTicketUsageDetail(ticket: AttendanceTicketDetails): string {
    if (ticket.checked_in_at) {
      return t("admin.reports.attendanceDetail.usage.checkedInAt", {
        date: formatLongDateTime(ticket.checked_in_at, i18n.language),
      });
    }

    if (isTicketCancelled(ticket)) {
      return t("admin.reports.attendanceDetail.usage.cancelledDetail");
    }

    return isTicketReadyForEntry(ticket)
      ? t("admin.reports.attendanceDetail.usage.notUsedDetail")
      : t("admin.reports.attendanceDetail.usage.notCheckedInDetail");
  }

  const visibleTickets = useMemo(() => {
    const tickets = details?.occupied_tickets ?? [];
    const filteredTickets = tickets.filter((ticket) => {
      if (!normalizedQuery) {
        return true;
      }

      const seatLabel = buildSeatKey(ticket.seat_row, ticket.seat_number);
      const searchParts = [
        seatLabel,
        ticket.user_name ?? "",
        ticket.user_email ?? "",
        ticket.status,
        ticket.order_status ?? "",
        getTicketUsageLabel(ticket),
        getTicketUsageDetail(ticket),
        formatLongDateTime(ticket.purchased_at, i18n.language),
        ticket.checked_in_at ? formatLongDateTime(ticket.checked_in_at, i18n.language) : "",
      ];

      return searchParts.join(" ").toLowerCase().includes(normalizedQuery);
    });

    return [...filteredTickets].sort((left, right) => {
      if (sortOption === "latest") {
        return new Date(right.purchased_at).getTime() - new Date(left.purchased_at).getTime();
      }

      if (sortOption === "oldest") {
        return new Date(left.purchased_at).getTime() - new Date(right.purchased_at).getTime();
      }

      if (left.seat_row === right.seat_row) {
        return left.seat_number - right.seat_number;
      }

      return left.seat_row - right.seat_row;
    });
  }, [
    details?.occupied_tickets,
    details?.session.start_time,
    details?.session.status,
    i18n.language,
    normalizedQuery,
    sortOption,
    t,
  ]);

  const selectedTicket = useMemo(
    () =>
      details?.occupied_tickets.find(
        (ticket) => buildSeatKey(ticket.seat_row, ticket.seat_number) === selectedSeatKey,
      ) ?? null,
    [details?.occupied_tickets, selectedSeatKey],
  );

  async function handlePdfExport() {
    if (!details || isExporting) {
      return;
    }

    setIsExporting(true);
    setFeedback(null);

    try {
      await exportAttendanceSessionPdf(details, i18n.language);
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("admin.reports.attendanceDetail.exportErrorTitle"),
        message:
          error instanceof Error && error.message
            ? error.message
            : t("admin.reports.attendanceDetail.exportErrorMessage"),
      });
    } finally {
      setIsExporting(false);
    }
  }

  function handleSeatSelection(seat: SeatAvailability) {
    if (seat.is_available) {
      setSelectedSeatKey("");
      return;
    }

    const nextSeatKey = buildSeatKey(seat.row, seat.number);
    setSelectedSeatKey((current) => (current === nextSeatKey ? "" : nextSeatKey));
  }

  function handleTicketSelection(ticket: AttendanceTicketDetails) {
    const nextSeatKey = buildSeatKey(ticket.seat_row, ticket.seat_number);
    setSelectedSeatKey((current) => (current === nextSeatKey ? "" : nextSeatKey));
  }

  if (isLoading) {
    return (
      <StatePanel
        tone="loading"
        title={t("admin.reports.attendanceDetail.loadingTitle")}
        message={t("admin.reports.attendanceDetail.loadingMessage")}
      />
    );
  }

  if (isNotFound) {
    return (
      <StatePanel
        tone="empty"
        title={t("admin.reports.attendanceDetail.notFoundTitle")}
        message={t("admin.reports.attendanceDetail.notFoundText")}
        action={
          <Link className="button--ghost" to="/admin">
            {t("common.actions.backToAdmin")}
          </Link>
        }
      />
    );
  }

  if (errorMessage || !details) {
    return (
      <StatePanel
        tone="error"
        title={t("admin.reports.attendanceDetail.errorTitle")}
        message={errorMessage || t("admin.reports.attendanceDetail.errorMessage")}
        action={
          <div className="actions-row">
            <Link className="button--ghost" to="/admin">
              {t("common.actions.backToAdmin")}
            </Link>
            <button className="button--ghost" type="button" onClick={() => void loadAttendanceDetails()}>
              {t("common.actions.retry")}
            </button>
          </div>
        }
      />
    );
  }

  const movieTitle = getLocalizedText(details.session.movie.title, i18n.language);
  const movieDescription = getLocalizedText(details.session.movie.description, i18n.language);
  const occupiedSeats = details.tickets_sold;
  const freeSeats = details.seat_map.available_seats;
  const totalSeats = details.session.total_seats;
  const buyerFallback = t("admin.reports.attendanceDetail.buyers.buyerFallback");
  const generatedLabel = t("admin.reports.attendanceDetail.generatedLabel", {
    date: formatLongDateTime(details.generated_at, i18n.language),
  });
  const hallLayoutLabel = t("admin.reports.attendanceDetail.hallLayout", {
    rows: details.seat_map.rows_count,
    seats: details.seat_map.seats_per_row,
  });
  const selectedSeatLabel = selectedTicket
    ? buildSeatKey(selectedTicket.seat_row, selectedTicket.seat_number)
    : "";
  const latestTicket =
    [...details.occupied_tickets].sort(
      (left, right) => new Date(right.purchased_at).getTime() - new Date(left.purchased_at).getTime(),
    )[0] ?? null;
  const latestTicketSeatLabel = latestTicket
    ? buildSeatKey(latestTicket.seat_row, latestTicket.seat_number)
    : "";
  const uniqueBuyerCount = new Set(details.occupied_tickets.map((ticket) => ticket.user_id)).size;
  const usedTicketsCount = details.occupied_tickets.filter((ticket) => Boolean(ticket.checked_in_at)).length;
  const validForEntryCount = details.occupied_tickets.filter((ticket) => isTicketReadyForEntry(ticket)).length;
  const selectedTicketBuyerName = selectedTicket?.user_name || buyerFallback;
  const latestTicketBuyerName = latestTicket?.user_name || buyerFallback;
  const sessionDateLabel = formatShortDate(details.session.start_time, i18n.language);
  const sessionTimeRange = `${formatTime(details.session.start_time, i18n.language)}-${formatTime(details.session.end_time, i18n.language)}`;

  return (
    <>
      {feedback ? (
        <StatusBanner tone={feedback.tone} title={feedback.title} message={feedback.message} />
      ) : null}

      <section className="page-header admin-attendance-detail-hero">
        <div className="admin-attendance-detail-hero__main">
          <div className="admin-attendance-detail-hero__copy">
            <div className="admin-attendance-detail-hero__eyebrow-row">
              <p className="page-eyebrow">{t("admin.reports.attendanceDetail.eyebrow")}</p>
              <div className="stats-row admin-attendance-detail-hero__badges">
                <span className="badge">{formatStateLabel(details.session.status)}</span>
                <span className="badge">{hallLayoutLabel}</span>
              </div>
            </div>

            <h1 className="page-title">{movieTitle}</h1>
            <p className="admin-attendance-detail-hero__session-line">
              {sessionDateLabel} | {sessionTimeRange}
            </p>

            {movieDescription ? (
              <p className="page-subtitle admin-attendance-detail-hero__description">{movieDescription}</p>
            ) : null}

            <div className="admin-attendance-detail-hero__quick-stats">
              <article className="admin-attendance-detail-hero__quick-stat">
                <span>{t("admin.reports.attendance.fillRate")}</span>
                <strong>{formatPercent(details.attendance_rate, i18n.language)}</strong>
                <p>{t("admin.reports.attendance.soldOfTotal", { sold: occupiedSeats, total: totalSeats })}</p>
              </article>
              <article className="admin-attendance-detail-hero__quick-stat">
                <span>{t("common.labels.ticketsSold")}</span>
                <strong>{occupiedSeats}</strong>
                <p>{t("admin.reports.attendanceDetail.buyers.results", { count: details.occupied_tickets.length })}</p>
              </article>
              <article className="admin-attendance-detail-hero__quick-stat">
                <span>{t("common.labels.availableSeats")}</span>
                <strong>{freeSeats}</strong>
                <p>{t("admin.reports.attendanceDetail.summary.availableDetail")}</p>
              </article>
            </div>
          </div>
        </div>

        <aside className="admin-attendance-detail-hero__aside">
          <div className="admin-attendance-detail-hero__aside-body">
            <div className="admin-attendance-detail-hero__fact-grid">
              <article className="admin-attendance-detail-hero__fact">
                <span>{t("common.labels.dateTime")}</span>
                <strong>{sessionDateLabel}</strong>
                <p>{sessionTimeRange}</p>
              </article>
              <article className="admin-attendance-detail-hero__fact">
                <span>{t("common.labels.price")}</span>
                <strong>{formatCurrency(details.session.price, i18n.language)}</strong>
                <p>{t("admin.reports.attendanceDetail.summary.priceDetail")}</p>
              </article>
              <article className="admin-attendance-detail-hero__fact">
                <span>{t("common.labels.status")}</span>
                <strong>{formatStateLabel(details.session.status)}</strong>
                <p>{hallLayoutLabel}</p>
              </article>
              <article className="admin-attendance-detail-hero__fact">
                <span>{t("common.labels.users")}</span>
                <strong>{uniqueBuyerCount}</strong>
                <p>{t("admin.reports.attendanceDetail.buyers.results", { count: details.occupied_tickets.length })}</p>
              </article>
            </div>

            <p className="muted admin-attendance-detail-hero__generated">{generatedLabel}</p>

            <div className="actions-row admin-attendance-detail-hero__actions">
              <Link className="button--ghost" to="/admin">
                {t("common.actions.backToAdmin")}
              </Link>
              <button
                className="button"
                type="button"
                disabled={isRefreshing || isExporting}
                onClick={() => void handlePdfExport()}
              >
                {isExporting ? t("admin.reports.attendanceDetail.exportLoading") : t("common.actions.downloadPdf")}
              </button>
              <button
                className="button--ghost"
                type="button"
                disabled={isRefreshing || isExporting}
                onClick={() => void loadAttendanceDetails({ background: true })}
              >
                {isRefreshing ? t("session.refresh.loading") : t("session.refresh.idle")}
              </button>
            </div>
          </div>
        </aside>
      </section>

      <section className="admin-attendance-detail-summary">
        <article className="card admin-attendance-detail-summary__card admin-attendance-detail-summary__card--feature">
          <div className="admin-attendance-detail-summary__feature-head">
            <div>
              <span className="admin-report-summary__eyebrow">{t("admin.reports.attendance.fillRate")}</span>
              <strong className="admin-attendance-detail-summary__feature-value">
                {formatPercent(details.attendance_rate, i18n.language)}
              </strong>
            </div>
            <span className="badge">{hallLayoutLabel}</span>
          </div>
          <p className="muted admin-attendance-detail-summary__feature-copy">
            {t("admin.reports.attendance.soldOfTotal", { sold: occupiedSeats, total: totalSeats })}
          </p>
          <div className="admin-attendance-detail-summary__progress" aria-hidden="true">
            <span style={{ width: `${Math.max(0, Math.min(details.attendance_rate * 100, 100))}%` }} />
          </div>
          <div className="admin-attendance-detail-summary__metrics">
            <div>
              <span>{t("common.labels.ticketsSold")}</span>
              <strong>{occupiedSeats}</strong>
            </div>
            <div>
              <span>{t("common.labels.availableSeats")}</span>
              <strong>{freeSeats}</strong>
            </div>
            <div>
              <span>{t("admin.reports.attendance.capacity")}</span>
              <strong>{totalSeats}</strong>
            </div>
          </div>
        </article>

        <article className="card admin-attendance-detail-summary__card">
          <span className="admin-report-summary__eyebrow">{t("common.labels.ticketsSold")}</span>
          <strong>{occupiedSeats}</strong>
          <p className="muted">{t("admin.reports.attendance.soldOfTotal", { sold: occupiedSeats, total: totalSeats })}</p>
        </article>
        <article className="card admin-attendance-detail-summary__card">
          <span className="admin-report-summary__eyebrow">{t("common.labels.availableSeats")}</span>
          <strong>{freeSeats}</strong>
          <p className="muted">{t("admin.reports.attendanceDetail.summary.availableDetail")}</p>
        </article>
        <article className="card admin-attendance-detail-summary__card">
          <span className="admin-report-summary__eyebrow">{t("common.labels.price")}</span>
          <strong>{formatCurrency(details.session.price, i18n.language)}</strong>
          <p className="muted">{t("admin.reports.attendanceDetail.summary.priceDetail")}</p>
        </article>
        <article className="card admin-attendance-detail-summary__card">
          <span className="admin-report-summary__eyebrow">{t("common.labels.users")}</span>
          <strong>{uniqueBuyerCount}</strong>
          <p className="muted">{t("admin.reports.attendanceDetail.buyers.results", {
            count: details.occupied_tickets.length,
          })}</p>
        </article>
      </section>

      <section className="card admin-attendance-detail-section">
        <div className="admin-attendance-detail-section__header">
          <div>
            <p className="page-eyebrow">{t("booking.seatMap.title")}</p>
            <h2 className="section-title">{t("admin.reports.attendanceDetail.seatMap.title")}</h2>
            <p className="muted">{t("admin.reports.attendanceDetail.seatMap.intro")}</p>
          </div>
          <div className="stats-row">
            <span className="badge">{occupiedSeats} {t("booking.seatMap.legend.occupied").toLowerCase()}</span>
            <span className="badge">{freeSeats} {t("booking.seatMap.legend.available").toLowerCase()}</span>
          </div>
        </div>

        <div className="seat-map admin-attendance-seat-map">
          <div className="seat-map__topline">
            <div>
              <h3>{t("booking.seatMap.title")}</h3>
              <p className="muted">{t("admin.reports.attendanceDetail.seatMap.selectionIntro")}</p>
            </div>
            <div className={`seat-map__selection${selectedTicket ? " is-active" : ""}`}>
              {selectedTicket ? (
                <>
                  {t("admin.reports.attendanceDetail.seatMap.selectedSeat", {
                    seat: selectedSeatLabel,
                    buyer: selectedTicket.user_name || t("admin.reports.attendanceDetail.buyers.buyerFallback"),
                  })}
                </>
              ) : (
                t("admin.reports.attendanceDetail.seatMap.selectionEmpty")
              )}
            </div>
          </div>

          <div className="seat-map__legend" role="group" aria-label={t("booking.seatMap.legend.label")}>
            <span className="seat-map__legend-item">
              <span className="seat-map__legend-swatch seat-map__legend-swatch--free" aria-hidden="true" />
              {t("booking.seatMap.legend.available")}
            </span>
            <span className="seat-map__legend-item">
              <span className="seat-map__legend-swatch seat-map__legend-swatch--selected" aria-hidden="true" />
              {t("booking.seatMap.legend.selected")}
            </span>
            <span className="seat-map__legend-item">
              <span className="seat-map__legend-swatch seat-map__legend-swatch--taken" aria-hidden="true" />
              {t("booking.seatMap.legend.occupied")}
            </span>
          </div>

          {groupedRows.length > 0 ? (
            <div className="seat-map__shell">
              <div className="seat-map__screen" aria-hidden="true">
                <span>{t("booking.seatMap.screen")}</span>
              </div>
              <div className="seat-map__viewport">
                <div className="seat-map__layout" role="group" aria-label={t("booking.seatMap.seatingArea")}>
                  {groupedRows.map((rowGroup) => (
                    <div
                      key={rowGroup.row}
                      className="seat-map__row"
                      role="group"
                      aria-label={t("booking.seatMap.rowLabel", { row: rowGroup.row })}
                    >
                      <span className="seat-map__row-label" aria-hidden="true">
                        {t("booking.seatMap.rowLabel", { row: rowGroup.row })}
                      </span>
                      <div className="seat-grid" role="presentation">
                        {rowGroup.seats.map((seat) => {
                          const seatKey = buildSeatKey(seat.row, seat.number);
                          const isOccupied = occupiedSeatKeys.has(seatKey);
                          const isSelected = selectedSeatKey === seatKey;

                          return (
                            <button
                              key={seatKey}
                              type="button"
                              className={`seat ${seat.is_available ? "seat--free" : "seat--taken"}${
                                isSelected ? " seat--selected" : ""
                              } admin-attendance-seat-map__seat${isOccupied ? " is-occupied" : " is-available"}`}
                              aria-pressed={isSelected}
                              aria-label={`${t("common.labels.row")} ${seat.row}, ${t("common.labels.seat").toLowerCase()} ${seat.number}, ${
                                seat.is_available
                                  ? t("booking.seatMap.legend.available").toLowerCase()
                                  : t("booking.seatMap.legend.occupied").toLowerCase()
                              }`}
                              onClick={() => handleSeatSelection(seat)}
                              title={`${t("common.labels.row")} ${seat.row}, ${t("common.labels.seat")} ${seat.number}`}
                            >
                              <span className="seat__number">{seat.number}</span>
                            </button>
                          );
                        })}
                      </div>
                      <span className="seat-map__row-label seat-map__row-label--mirror" aria-hidden="true">
                        {t("booking.seatMap.rowLabel", { row: rowGroup.row })}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <section className="empty-state empty-state--panel">
              <h2>{t("booking.seatMap.unavailable")}</h2>
            </section>
          )}
        </div>
      </section>

      <section className="card admin-attendance-detail-section admin-attendance-detail-section--buyers">
        <div className="admin-attendance-detail-section__header">
          <div>
            <p className="page-eyebrow">{t("admin.reports.bookings.eyebrow")}</p>
            <h2 className="section-title">{t("admin.reports.attendanceDetail.buyers.title")}</h2>
            <p className="muted">{t("admin.reports.attendanceDetail.buyers.intro")}</p>
          </div>
          <div className="admin-attendance-detail-buyers__meta">
            <span className="badge">{t("admin.reports.attendanceDetail.buyers.results", {
              count: visibleTickets.length,
            })}</span>
            <span className="badge">
              {uniqueBuyerCount} {t("common.labels.users")}
            </span>
            <span className="badge">
              {t("admin.reports.attendanceDetail.usage.readyCount", { count: validForEntryCount })}
            </span>
            <span className="badge">
              {t("admin.reports.attendanceDetail.usage.usedCount", { count: usedTicketsCount })}
            </span>
            {selectedTicket ? <span className="badge">{selectedSeatLabel}</span> : null}
          </div>
        </div>

        <div className="admin-attendance-detail-buyers__overview">
          <article className="admin-attendance-detail-buyers__card admin-attendance-detail-buyers__card--spotlight">
            <span className="admin-report-summary__eyebrow">{t("common.labels.seat")}</span>
            {selectedTicket ? (
              <>
                <div className="admin-attendance-detail-buyers__spotlight-head">
                  <span className="admin-attendance-seat-chip">{selectedSeatLabel}</span>
                  <div className="admin-attendance-detail-buyers__identity">
                    <strong>{selectedTicketBuyerName}</strong>
                    <span>{selectedTicket.user_email || "-"}</span>
                  </div>
                </div>
                <div className="stats-row">
                  <span className="badge">{formatLongDateTime(selectedTicket.purchased_at, i18n.language)}</span>
                  <span className={`admin-attendance-status-chip ${buildStatusToneClass(selectedTicket.status)}`}>
                    {formatStateLabel(selectedTicket.status)}
                  </span>
                  <span className={`admin-attendance-status-chip ${buildUsageToneClass(selectedTicket)}`}>
                    {getTicketUsageLabel(selectedTicket)}
                  </span>
                  {selectedTicket.checked_in_at ? (
                    <span className="badge">{getTicketUsageDetail(selectedTicket)}</span>
                  ) : null}
                  <span
                    className={`admin-attendance-status-chip ${buildStatusToneClass(selectedTicket.order_status)}`}
                  >
                    {selectedTicket.order_status
                      ? formatStateLabel(selectedTicket.order_status)
                      : t("admin.reports.attendanceDetail.buyers.noOrderStatus")}
                  </span>
                </div>
              </>
            ) : (
              <div className="admin-attendance-detail-buyers__spotlight-empty">
                <strong>{t("admin.reports.attendanceDetail.seatMap.selectionEmpty")}</strong>
                <p className="muted">{t("admin.reports.attendanceDetail.seatMap.selectionIntro")}</p>
              </div>
            )}
          </article>

          <article className="admin-attendance-detail-buyers__card">
            <span className="admin-report-summary__eyebrow">{t("admin.reports.attendanceDetail.table.purchasedAt")}</span>
            <strong>{latestTicket ? formatLongDateTime(latestTicket.purchased_at, i18n.language) : "-"}</strong>
            <p className="muted">
              {latestTicket
                ? `${latestTicketBuyerName} | ${latestTicketSeatLabel}`
                : t("admin.reports.attendanceDetail.buyers.emptyText")}
            </p>
          </article>

          <article className="admin-attendance-detail-buyers__card">
            <span className="admin-report-summary__eyebrow">{t("common.labels.status")}</span>
            <strong>{formatStateLabel(details.session.status)}</strong>
            <p className="muted">{generatedLabel}</p>
          </article>
        </div>

        <div className="admin-attendance-detail-toolbar">
          <label className="field field--search">
            <span>{t("admin.reports.attendanceDetail.buyers.searchLabel")}</span>
            <input
              type="search"
              value={searchQuery}
              placeholder={t("admin.reports.attendanceDetail.buyers.searchPlaceholder")}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </label>

          <label className="field">
            <span>{t("admin.reports.attendanceDetail.buyers.sortLabel")}</span>
            <select
              value={sortOption}
              onChange={(event) => setSortOption(event.target.value as TicketSortOption)}
            >
              <option value="seat">{t("admin.reports.attendanceDetail.buyers.sort.seat")}</option>
              <option value="latest">{t("admin.reports.attendanceDetail.buyers.sort.latest")}</option>
              <option value="oldest">{t("admin.reports.attendanceDetail.buyers.sort.oldest")}</option>
            </select>
          </label>

          <div className="toolbar__actions">
            <button
              className="button--ghost"
              type="button"
              onClick={() => {
                setSearchQuery("");
                setSortOption("seat");
                setSelectedSeatKey("");
              }}
            >
              {t("common.actions.resetFilters")}
            </button>
          </div>
        </div>

        {details.occupied_tickets.length === 0 ? (
          <section className="empty-state empty-state--panel">
            <h2>{t("admin.reports.attendanceDetail.buyers.emptyTitle")}</h2>
            <p>{t("admin.reports.attendanceDetail.buyers.emptyText")}</p>
          </section>
        ) : visibleTickets.length === 0 ? (
          <section className="empty-state empty-state--panel">
            <h2>{t("admin.reports.attendanceDetail.buyers.filteredEmptyTitle")}</h2>
            <p>{t("admin.reports.attendanceDetail.buyers.filteredEmptyText")}</p>
            <button
              className="button--ghost"
              type="button"
              onClick={() => {
                setSearchQuery("");
                setSortOption("seat");
              }}
            >
              {t("common.actions.resetFilters")}
            </button>
          </section>
        ) : (
          <div className="admin-attendance-table-wrap">
            <table className="admin-attendance-table">
              <thead>
                <tr>
                  <th>{t("common.labels.seat")}</th>
                  <th>{t("common.labels.users")}</th>
                  <th>{t("admin.reports.attendanceDetail.table.purchasedAt")}</th>
                  <th>{t("admin.reports.attendanceDetail.table.ticketStatus")}</th>
                  <th>{t("admin.reports.attendanceDetail.table.entryUse")}</th>
                  <th>{t("admin.reports.attendanceDetail.table.orderStatus")}</th>
                </tr>
              </thead>
              <tbody>
                {visibleTickets.map((ticket) => {
                  const seatKey = buildSeatKey(ticket.seat_row, ticket.seat_number);
                  const isSelected = seatKey === selectedSeatKey;

                  return (
                    <tr
                      key={ticket.id}
                      className={isSelected ? "is-selected" : ""}
                      onClick={() => handleTicketSelection(ticket)}
                    >
                      <td data-label={t("common.labels.seat")}>
                        <span className="admin-attendance-seat-chip">{seatKey}</span>
                      </td>
                      <td data-label={t("common.labels.users")}>
                        <div className="admin-attendance-table__buyer">
                          <strong>{ticket.user_name || buyerFallback}</strong>
                          <span>{ticket.user_email || "-"}</span>
                        </div>
                      </td>
                      <td data-label={t("admin.reports.attendanceDetail.table.purchasedAt")}>
                        <div className="admin-attendance-table__timestamp">
                          <strong>{formatLongDateTime(ticket.purchased_at, i18n.language)}</strong>
                          <span>{t("common.labels.price")}: {formatCurrency(ticket.price, i18n.language)}</span>
                        </div>
                      </td>
                      <td data-label={t("admin.reports.attendanceDetail.table.ticketStatus")}>
                        <span className={`admin-attendance-status-chip ${buildStatusToneClass(ticket.status)}`}>
                          {formatStateLabel(ticket.status)}
                        </span>
                      </td>
                      <td data-label={t("admin.reports.attendanceDetail.table.entryUse")}>
                        <div className="admin-attendance-table__usage">
                          <span className={`admin-attendance-status-chip ${buildUsageToneClass(ticket)}`}>
                            {getTicketUsageLabel(ticket)}
                          </span>
                          <small>{getTicketUsageDetail(ticket)}</small>
                        </div>
                      </td>
                      <td data-label={t("admin.reports.attendanceDetail.table.orderStatus")}>
                        <span
                          className={`admin-attendance-status-chip ${buildStatusToneClass(ticket.order_status)}`}
                        >
                          {ticket.order_status
                            ? formatStateLabel(ticket.order_status)
                            : t("admin.reports.attendanceDetail.buyers.noOrderStatus")}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
