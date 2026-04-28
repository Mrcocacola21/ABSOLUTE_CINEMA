import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import "./AdminOrderValidationPage.css";

import { checkInOrderRequest, validateOrderTokenRequest } from "@/api/admin";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getLocalizedText } from "@/shared/localization";
import { formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { OrderValidationResult } from "@/types/domain";

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

  return (
    <div className="admin-validation-page">
      <section className="page-header admin-validation-hero">
        <div>
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
      </form>

      {errorMessage ? <StatusBanner tone="error" message={errorMessage} /> : null}
      {feedbackMessage ? <StatusBanner tone="success" message={feedbackMessage} /> : null}

      {result ? (
        <section className={`panel admin-validation-result ${validityClass}`}>
          <div className="admin-validation-result__status">
            <span className={`order-detail-validity ${validityClass}`}>
              {statusLabel}
            </span>
            <span className="badge">{formatStateLabel(result.validity_code)}</span>
            <span className="badge">{formatStateLabel(result.token_status)}</span>
          </div>

          <div className="admin-validation-result__headline">
            <h2 className="section-title">
              {movieTitle || t("admin.validation.noOrderTitle", { defaultValue: "No order loaded" })}
            </h2>
            <p>{result.message}</p>
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
              <span>{t("common.labels.dateTime")}</span>
              <strong>
                {result.session_start_time ? formatDateTime(result.session_start_time, i18n.language) : "-"}
              </strong>
            </div>
            <div>
              <span>{t("common.labels.tickets")}</span>
              <strong>
                {result.active_tickets_count} / {result.active_tickets_count + result.cancelled_tickets_count}
              </strong>
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
          </div>

          {result.tickets.length > 0 ? (
            <div className="admin-validation-ticket-list">
              {result.tickets.map((ticket) => (
                <article
                  key={ticket.id}
                  className={`admin-validation-ticket ${ticket.valid_for_entry ? "is-valid" : "is-invalid"}`}
                >
                  <strong>
                    {t("admin.validation.seat", {
                      defaultValue: "Row {{row}}, seat {{seat}}",
                      row: ticket.seat_row,
                      seat: ticket.seat_number,
                    })}
                  </strong>
                  <span className="badge">{formatStateLabel(ticket.status)}</span>
                  <span className={`order-detail-validity ${ticket.valid_for_entry ? "is-valid" : "is-invalid"}`}>
                    {ticket.valid_for_entry
                      ? t("admin.validation.ticketValid", { defaultValue: "Entry valid" })
                      : ticket.checked_in_at
                        ? t("admin.validation.ticketUsed", { defaultValue: "Already used" })
                        : t("admin.validation.ticketInvalid", { defaultValue: "Entry not valid" })}
                  </span>
                  {ticket.checked_in_at ? (
                    <span className="admin-validation-ticket__time">
                      {t("admin.validation.checkedInAt", {
                        defaultValue: "Checked in {{date}}",
                        date: formatDateTime(ticket.checked_in_at, i18n.language),
                      })}
                    </span>
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
