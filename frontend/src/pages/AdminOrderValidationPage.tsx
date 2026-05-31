import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import "./AdminOrderValidationPage.css";

import { checkInOrderRequest, validateOrderTokenRequest } from "@/api/admin";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getLocalizedText } from "@/shared/localization";
import { formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { OrderValidationResult, OrderValidationTicket } from "@/types/domain";

function normalizeValidationInput(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }

  try {
    const parsed = new URL(trimmed);
    const tokenFromQuery = parsed.searchParams.get("token");
    if (tokenFromQuery) {
      return tokenFromQuery.trim();
    }

    const pathSegments = parsed.pathname.split("/").filter(Boolean);
    return decodeURIComponent(pathSegments[pathSegments.length - 1] ?? "").trim();
  } catch {
    return trimmed;
  }
}

function getTicketEntryLabel(ticket: OrderValidationTicket, t: ReturnType<typeof useTranslation>["t"]) {
  if (ticket.valid_for_entry) {
    return t("admin.validation.ticketValid", { defaultValue: "Entry valid" });
  }
  if (ticket.checked_in_at) {
    return t("admin.validation.ticketUsed", { defaultValue: "Already used" });
  }
  return t("admin.validation.ticketInvalid", { defaultValue: "Entry not valid" });
}

function getTicketEntryClass(ticket: OrderValidationTicket) {
  if (ticket.valid_for_entry) {
    return "is-valid";
  }
  if (ticket.checked_in_at) {
    return "is-already_used";
  }
  return "is-invalid";
}

export function AdminOrderValidationPage() {
  const { token } = useParams<{ token?: string }>();
  const { t, i18n } = useTranslation();
  const initialToken = useMemo(() => normalizeValidationInput(token ?? ""), [token]);
  const [tokenInput, setTokenInput] = useState(initialToken);
  const [result, setResult] = useState<OrderValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isCheckingIn, setIsCheckingIn] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");

  async function validateToken(rawToken: string) {
    const normalizedToken = normalizeValidationInput(rawToken);
    if (!normalizedToken) {
      setResult(null);
      setErrorMessage(
        t("admin.validation.emptyToken", {
          defaultValue: "Paste a scanned QR URL or validation token first.",
        }),
      );
      return;
    }

    setTokenInput(normalizedToken);
    setIsValidating(true);
    setErrorMessage("");
    setFeedbackMessage("");
    try {
      const response = await validateOrderTokenRequest(normalizedToken);
      setResult(response.data);
    } catch (error) {
      setResult(null);
      setErrorMessage(
        extractApiErrorMessage(
          error,
          t("admin.validation.unavailable", { defaultValue: "Order validation is currently unavailable." }),
        ),
      );
    } finally {
      setIsValidating(false);
    }
  }

  useEffect(() => {
    setTokenInput(initialToken);
    if (initialToken) {
      void validateToken(initialToken);
    }
  }, [initialToken]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void validateToken(tokenInput);
  }

  async function handleCheckIn() {
    if (!result?.order_id || !result.can_check_in) {
      return;
    }

    setIsCheckingIn(true);
    setErrorMessage("");
    setFeedbackMessage("");
    try {
      const response = await checkInOrderRequest(result.order_id);
      setResult(response.data);
      setFeedbackMessage(
        t("admin.validation.checkInSuccess", {
          defaultValue: "Entry confirmed. This QR now validates as already used.",
        }),
      );
    } catch (error) {
      setErrorMessage(
        extractApiErrorMessage(
          error,
          t("admin.validation.checkInFailed", { defaultValue: "The order could not be checked in." }),
        ),
      );
      if (tokenInput) {
        void validateToken(tokenInput);
      }
    } finally {
      setIsCheckingIn(false);
    }
  }

  const movieTitle = result?.movie_title ? getLocalizedText(result.movie_title, i18n.language) : "";
  const validityClass = result?.validity_code === "valid" ? "is-valid" : `is-${result?.validity_code ?? "idle"}`;
  const statusLabel =
    result?.validity_code === "valid"
      ? t("admin.validation.valid", { defaultValue: "Valid" })
      : result?.validity_code === "cancelled"
        ? t("admin.validation.cancelled", { defaultValue: "Cancelled" })
        : result?.validity_code === "expired"
          ? t("admin.validation.expired", { defaultValue: "Expired" })
          : result?.validity_code === "already_used"
            ? t("admin.validation.alreadyUsed", { defaultValue: "Already used" })
            : t("admin.validation.invalid", { defaultValue: "Invalid" });
  const totalTickets = result?.tickets.length ?? 0;
  const decisionLabel = result?.is_valid_for_entry
    ? t("admin.validation.entryAllowed", { defaultValue: "Entry allowed" })
    : t("admin.validation.entryDenied", { defaultValue: "Entry denied" });
  const decisionClass = result?.is_valid_for_entry ? "is-allowed" : "is-denied";

  return (
    <div className="admin-validation-page">
      <section className="page-header admin-validation-hero">
        <div className="admin-validation-hero__copy">
          <p className="page-eyebrow">
            {t("admin.validation.eyebrow", { defaultValue: "Staff validation" })}
          </p>
          <h1 className="page-title">
            {t("admin.validation.title", { defaultValue: "Order QR check" })}
          </h1>
          <p className="page-subtitle">
            {t("admin.validation.intro", {
              defaultValue: "Scan or paste the QR payload from a customer PDF to verify live order validity.",
            })}
          </p>
        </div>
        <Link to="/admin" className="button--ghost">
          {t("common.actions.backToAdmin")}
        </Link>
      </section>

      <form className="panel admin-validation-form" onSubmit={handleSubmit}>
        <div className="admin-validation-form__intro">
          <h2>{t("admin.validation.inputTitle", { defaultValue: "Validate QR token" })}</h2>
          <p>{t("admin.validation.inputHint", { defaultValue: "Paste the scanned QR URL or signed token exactly as received." })}</p>
        </div>
        <div className="admin-validation-form__controls">
          <label className="field">
            <span>{t("admin.validation.inputLabel", { defaultValue: "QR payload or token" })}</span>
            <input
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
              placeholder={t("admin.validation.inputPlaceholder", {
                defaultValue: "Paste scanned URL or signed token",
              })}
              disabled={isValidating}
            />
          </label>
          <button className="button" type="submit" disabled={isValidating}>
            {isValidating
              ? t("admin.validation.validating", { defaultValue: "Validating..." })
              : t("admin.validation.validate", { defaultValue: "Validate order" })}
          </button>
        </div>
      </form>

      {errorMessage ? <StatusBanner tone="error" message={errorMessage} /> : null}
      {feedbackMessage ? <StatusBanner tone="success" message={feedbackMessage} /> : null}

      {!result && isValidating ? (
        <StatePanel
          tone="loading"
          title={t("admin.validation.loadingTitle")}
          message={t("admin.validation.loadingMessage")}
        />
      ) : null}

      {!result && !isValidating && !errorMessage ? (
        <StatePanel
          tone="empty"
          title={t("admin.validation.idleTitle")}
          message={t("admin.validation.idleMessage")}
        />
      ) : null}

      {result ? (
        <section className={`panel admin-validation-result ${validityClass}`}>
          <div className="admin-validation-result__topline">
            <div className={`admin-validation-decision ${decisionClass}`}>
              <span className={`order-detail-validity order-detail-validity--primary ${validityClass}`}>
                {statusLabel}
              </span>
              <div>
                <strong>{decisionLabel}</strong>
                <p>{result.message}</p>
              </div>
            </div>

            <div className="admin-validation-result__status">
              <span className="admin-validation-meta-pill">
                {t("admin.validation.token", { defaultValue: "Token" })}: {formatStateLabel(result.token_status)}
              </span>
              <span className="admin-validation-meta-pill">
                {t("admin.validation.state", { defaultValue: "State" })}: {formatStateLabel(result.validity_code)}
              </span>
              <span className="admin-validation-meta-pill">
                {t("admin.validation.scannedAt", { defaultValue: "Scanned" })}:{" "}
                {formatDateTime(result.scanned_at, i18n.language)}
              </span>
            </div>
          </div>

          {result.can_check_in && result.order_id ? (
            <div className="admin-validation-action">
              <button className="button" type="button" disabled={isCheckingIn} onClick={() => void handleCheckIn()}>
                {isCheckingIn
                  ? t("admin.validation.checkingIn", { defaultValue: "Checking in..." })
                  : t("admin.validation.checkIn", { defaultValue: "Check in order" })}
              </button>
              <p>
                {t("admin.validation.checkInHint", {
                  defaultValue: "This confirms entry for every active unchecked ticket in the order.",
                })}
              </p>
            </div>
          ) : null}

          <div className="admin-validation-result__headline">
            <div>
              <p className="page-eyebrow">{t("admin.validation.result", { defaultValue: "Validation result" })}</p>
              <h2 className="section-title">
                {movieTitle || t("admin.validation.noOrderTitle", { defaultValue: "No order loaded" })}
              </h2>
            </div>
            <p>
              {t("admin.validation.ticketSummary", {
                defaultValue: "{{remaining}} tickets remain valid out of {{total}} tickets in this order.",
                remaining: result.unchecked_active_tickets_count,
                total: totalTickets,
              })}
            </p>
          </div>

          <section className="admin-validation-section">
            <div className="admin-validation-section__header">
              <h3>{t("admin.validation.orderSummary", { defaultValue: "Order summary" })}</h3>
            </div>
            <div className="admin-validation-facts">
              <div>
                <span>{t("admin.validation.orderId", { defaultValue: "Order id" })}</span>
                <strong>{result.order_id ?? t("admin.validation.none", { defaultValue: "None" })}</strong>
              </div>
              <div>
                <span>{t("common.labels.status")}</span>
                <strong>{result.order_status ? formatStateLabel(result.order_status) : "-"}</strong>
              </div>
              <div>
                <span>{t("common.labels.tickets")}</span>
                <strong>{totalTickets}</strong>
              </div>
              <div>
                <span>{t("admin.validation.checkedIn", { defaultValue: "Checked in" })}</span>
                <strong>
                  {result.checked_in_tickets_count} / {result.active_tickets_count}
                </strong>
              </div>
              <div>
                <span>{t("admin.validation.remaining", { defaultValue: "Remaining" })}</span>
                <strong>{result.unchecked_active_tickets_count}</strong>
              </div>
              <div>
                <span>{t("admin.validation.cancelledTickets", { defaultValue: "Cancelled" })}</span>
                <strong>{result.cancelled_tickets_count}</strong>
              </div>
            </div>
          </section>

          <section className="admin-validation-section admin-validation-context">
            <div className="admin-validation-section__header">
              <h3>{t("admin.validation.bookingContext", { defaultValue: "Booking context" })}</h3>
            </div>
            <div className="admin-validation-context__grid">
              <div>
                <span>{t("common.labels.movie")}</span>
                <strong>{movieTitle || "-"}</strong>
              </div>
              <div>
                <span>{t("common.labels.dateTime")}</span>
                <strong>{result.session_start_time ? formatDateTime(result.session_start_time, i18n.language) : "-"}</strong>
              </div>
              <div>
                <span>{t("admin.validation.sessionEnds", { defaultValue: "Session ends" })}</span>
                <strong>{result.session_end_time ? formatDateTime(result.session_end_time, i18n.language) : "-"}</strong>
              </div>
              <div>
                <span>{t("admin.validation.sessionStatus", { defaultValue: "Session status" })}</span>
                <strong>{result.session_status ? formatStateLabel(result.session_status) : "-"}</strong>
              </div>
            </div>
          </section>

          {result.tickets.length > 0 ? (
            <section className="admin-validation-section">
              <div className="admin-validation-section__header">
                <div>
                  <h3>{t("admin.validation.ticketList", { defaultValue: "Tickets in order" })}</h3>
                  <p>
                    {t("admin.validation.ticketListHint", {
                      defaultValue: "Each row shows the seat, ticket status, and entry result for staff.",
                    })}
                  </p>
                </div>
              </div>
              <div className="admin-validation-ticket-list">
                {result.tickets.map((ticket) => (
                  <article
                    key={ticket.id}
                    className={`admin-validation-ticket ${ticket.valid_for_entry ? "is-valid" : "is-invalid"} ${
                      ticket.checked_in_at ? "is-used" : ""
                    }`}
                  >
                    <div className="admin-validation-ticket__identity">
                      <span>{t("admin.validation.seatLabel", { defaultValue: "Seat" })}</span>
                      <strong>
                        {t("admin.validation.seat", {
                          defaultValue: "Row {{row}}, seat {{seat}}",
                          row: ticket.seat_row,
                          seat: ticket.seat_number,
                        })}
                      </strong>
                      <p>{ticket.id}</p>
                    </div>
                    <div className="admin-validation-ticket__state">
                      <span>{t("admin.validation.ticketState", { defaultValue: "Ticket state" })}</span>
                      <strong>{formatStateLabel(ticket.status)}</strong>
                      {ticket.cancelled_at ? (
                        <p>
                          {t("admin.validation.cancelledAt", {
                            defaultValue: "Cancelled {{date}}",
                            date: formatDateTime(ticket.cancelled_at, i18n.language),
                          })}
                        </p>
                      ) : null}
                    </div>
                    <div className="admin-validation-ticket__entry">
                      <span className={`order-detail-validity ${getTicketEntryClass(ticket)}`}>
                        {getTicketEntryLabel(ticket, t)}
                      </span>
                      <p>
                        {ticket.checked_in_at
                          ? t("admin.validation.checkedInAt", {
                              defaultValue: "Checked in {{date}}",
                              date: formatDateTime(ticket.checked_in_at, i18n.language),
                            })
                          : ticket.valid_for_entry
                            ? t("admin.validation.notCheckedIn", { defaultValue: "Not checked in yet" })
                            : t("admin.validation.noEntry", { defaultValue: "No entry permission" })}
                      </p>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
