import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import "./OrderDetailsPage.css";

import { downloadMyOrderPdfRequest, getMyOrderRequest } from "@/api/orders";
import {
  getOrderPaymentDetailsRequest,
  listOrderRefundsRequest,
  requestOrderRefundRequest,
} from "@/api/payments";
import { cancelTicketRequest } from "@/api/tickets";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getLocalizedText } from "@/shared/localization";
import { isPaidOrder, isPendingPaymentOrder } from "@/shared/payment";
import { resolvePosterSource } from "@/shared/posters";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { OrderDetails, OrderTicket, PaymentDetails, Refund, RefundStatus } from "@/types/domain";

function getInitials(value: string): string {
  return value
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("") || "CS";
}

function triggerPdfDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function getOrderTicketTimelineAt(ticket: OrderTicket, fallback: string): string {
  return ticket.purchased_at ?? ticket.reserved_at ?? ticket.expires_at ?? fallback;
}

function formatTicketTimeline(
  ticket: OrderTicket,
  fallback: string,
  t: TFunction,
  language: string,
): string {
  const baseDate = getOrderTicketTimelineAt(ticket, fallback);
  const baseText = ticket.purchased_at
    ? t("profile.orders.purchasedAt", { date: formatDateTime(baseDate, language) })
    : ticket.status === "expired"
      ? t("checkout.labels.expiredAt", { date: formatDateTime(baseDate, language) })
      : t("checkout.labels.reservedAt", { date: formatDateTime(baseDate, language) });
  const extraParts = [
    ticket.cancelled_at
      ? t("profile.orders.cancelledAt", { date: formatDateTime(ticket.cancelled_at, language) })
      : "",
    ticket.checked_in_at
      ? t("orderDetails.tickets.checkedInAt", {
          defaultValue: "Checked in {{date}}",
          date: formatDateTime(ticket.checked_in_at, language),
        })
      : "",
  ].filter(Boolean);

  return [baseText, ...extraParts].join(" | ");
}

function formatMinorAmount(amountMinor: number, currency: string | undefined, language: string): string {
  return new Intl.NumberFormat(language, {
    style: "currency",
    currency: currency || "UAH",
    maximumFractionDigits: 2,
  }).format(amountMinor / 100);
}

function getRefundStatusLabel(status: RefundStatus, t: TFunction): string {
  const fallbackByStatus: Record<RefundStatus, string> = {
    created: "Refund requested",
    pending: "Refund pending",
    succeeded: "Refunded",
    failed: "Refund failed",
    cancelled: "Refund cancelled",
  };
  return t(`orderDetails.refunds.status.${status}`, { defaultValue: fallbackByStatus[status] });
}

export function OrderDetailsPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { t, i18n } = useTranslation();
  const [order, setOrder] = useState<OrderDetails | null>(null);
  const [payment, setPayment] = useState<PaymentDetails | null>(null);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [cancellingTicketId, setCancellingTicketId] = useState<string | null>(null);
  const [refundingTarget, setRefundingTarget] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: "success" | "error" | "info";
    title?: string;
    message: string;
  } | null>(null);

  async function loadOrder(options?: { background?: boolean }) {
    if (!orderId) {
      setErrorMessage(t("orderDetails.errors.missingId", { defaultValue: "Order id is missing." }));
      setIsLoading(false);
      return;
    }

    if (!options?.background) {
      setIsLoading(true);
    }

    try {
      const [orderResponse, paymentResponse, refundsResponse] = await Promise.all([
        getMyOrderRequest(orderId),
        getOrderPaymentDetailsRequest(orderId).catch(() => null),
        listOrderRefundsRequest(orderId).catch(() => null),
      ]);
      setOrder(orderResponse.data);
      setPayment(paymentResponse?.data ?? null);
      setRefunds(refundsResponse?.data ?? []);
      setErrorMessage("");
    } catch (error) {
      setOrder(null);
      setPayment(null);
      setRefunds([]);
      setErrorMessage(
        extractApiErrorMessage(
          error,
          t("orderDetails.errors.unavailable", { defaultValue: "Order details are currently unavailable." }),
        ),
      );
    } finally {
      if (!options?.background) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadOrder();
  }, [orderId]);

  async function handleDownloadPdf() {
    if (!order) {
      return;
    }

    setIsDownloadingPdf(true);
    setFeedback(null);
    try {
      const blob = await downloadMyOrderPdfRequest(order.id);
      triggerPdfDownload(blob, `cinema-order-${order.id.slice(-8)}.pdf`);
      setFeedback({
        tone: "success",
        title: t("orderDetails.pdf.successTitle", { defaultValue: "PDF ready" }),
        message: t("orderDetails.pdf.successMessage", {
          defaultValue: "The order receipt PDF was generated with a staff validation QR code.",
        }),
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("orderDetails.pdf.errorTitle", { defaultValue: "PDF download failed" }),
        message: extractApiErrorMessage(
          error,
          t("orderDetails.pdf.errorMessage", { defaultValue: "The order PDF could not be generated." }),
        ),
      });
    } finally {
      setIsDownloadingPdf(false);
    }
  }

  async function handleCancelTicket(ticket: OrderTicket) {
    if (!order) {
      return;
    }

    const confirmed = window.confirm(
      t("orderDetails.tickets.cancelConfirm", {
        defaultValue: "Cancel ticket for row {{row}}, seat {{seat}}?",
        row: ticket.seat_row,
        seat: ticket.seat_number,
      }),
    );
    if (!confirmed) {
      return;
    }

    setCancellingTicketId(ticket.id);
    setFeedback(null);
    try {
      await cancelTicketRequest(ticket.id);
      await loadOrder({ background: true });
      setFeedback({
        tone: "success",
        title: t("orderDetails.tickets.cancelSuccessTitle", { defaultValue: "Ticket cancelled" }),
        message: t("orderDetails.tickets.cancelSuccessMessage", {
          defaultValue: "The order details were refreshed with the latest cancellation state.",
        }),
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("orderDetails.tickets.cancelErrorTitle", { defaultValue: "Ticket cancellation failed" }),
        message: extractApiErrorMessage(
          error,
          t("orderDetails.tickets.cancelErrorMessage", { defaultValue: "The ticket could not be cancelled." }),
        ),
      });
    } finally {
      setCancellingTicketId(null);
    }
  }

  async function handleTicketRefund(ticket: OrderTicket) {
    if (!order) {
      return;
    }

    const confirmed = window.confirm(
      t("orderDetails.refunds.ticketConfirm", {
        defaultValue: "Request a refund for row {{row}}, seat {{seat}}?",
        row: ticket.seat_row,
        seat: ticket.seat_number,
      }),
    );
    if (!confirmed) {
      return;
    }

    setRefundingTarget(`ticket:${ticket.id}`);
    setFeedback(null);
    try {
      const response = await requestOrderRefundRequest(order.id, {
        scope: "tickets",
        ticket_ids: [ticket.id],
        reason: "customer_cancelled_ticket",
      });
      setPayment(response.data.payment);
      setRefunds(response.data.refunds);
      await loadOrder({ background: true });
      setFeedback({
        tone: "success",
        title: t("orderDetails.refunds.requestSuccessTitle", { defaultValue: "Refund requested" }),
        message: t("orderDetails.refunds.ticketRequestSuccessMessage", {
          defaultValue: "The refund was created against the order payment and the status was refreshed.",
        }),
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("orderDetails.refunds.requestErrorTitle", { defaultValue: "Refund request failed" }),
        message: extractApiErrorMessage(
          error,
          t("orderDetails.refunds.requestErrorMessage", {
            defaultValue: "The refund request could not be created.",
          }),
        ),
      });
    } finally {
      setRefundingTarget(null);
    }
  }

  async function handleFullRefund() {
    if (!order) {
      return;
    }

    const confirmed = window.confirm(
      t("orderDetails.refunds.fullConfirm", {
        defaultValue: "Request a full refund for this cancelled order?",
      }),
    );
    if (!confirmed) {
      return;
    }

    setRefundingTarget("order");
    setFeedback(null);
    try {
      const response = await requestOrderRefundRequest(order.id, {
        scope: "order",
        reason: "customer_cancelled_order",
      });
      setPayment(response.data.payment);
      setRefunds(response.data.refunds);
      await loadOrder({ background: true });
      setFeedback({
        tone: "success",
        title: t("orderDetails.refunds.requestSuccessTitle", { defaultValue: "Refund requested" }),
        message: t("orderDetails.refunds.fullRequestSuccessMessage", {
          defaultValue: "The remaining refundable payment amount was submitted as a refund.",
        }),
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("orderDetails.refunds.requestErrorTitle", { defaultValue: "Refund request failed" }),
        message: extractApiErrorMessage(
          error,
          t("orderDetails.refunds.requestErrorMessage", {
            defaultValue: "The refund request could not be created.",
          }),
        ),
      });
    } finally {
      setRefundingTarget(null);
    }
  }

  if (isLoading) {
    return (
      <StatePanel
        tone="loading"
        title={t("orderDetails.loading.title", { defaultValue: "Loading order details" })}
        message={t("orderDetails.loading.message", {
          defaultValue: "Fetching your order, tickets, session information, and validation data.",
        })}
      />
    );
  }

  if (errorMessage || !order) {
    return (
      <StatePanel
        tone="error"
        title={t("orderDetails.errors.title", { defaultValue: "Unable to load this order" })}
        message={errorMessage}
        action={
          <div className="actions-row">
            <button className="button--ghost" type="button" onClick={() => void loadOrder()}>
              {t("common.actions.retry")}
            </button>
            <Link to="/profile" className="button">
              {t("orderDetails.actions.backToOrders", { defaultValue: "Back to my orders" })}
            </Link>
          </div>
        }
      />
    );
  }

  const movieTitle = getLocalizedText(order.movie_title, i18n.language);
  const shortOrderId = order.id.slice(-8).toUpperCase();
  const posterSource = resolvePosterSource(order);
  const validityClass = order.valid_for_entry ? "is-valid" : "is-invalid";
  const canDownloadPdf = isPaidOrder(order);
  const canContinueCheckout = isPendingPaymentOrder(order);
  const validTickets = order.tickets.filter((ticket) => ticket.valid_for_entry);
  const refundCurrency = payment?.currency ?? "UAH";
  const refundedAmount = order.refunded_amount_minor;
  const remainingRefundableAmount = order.remaining_refundable_amount_minor;
  const latestRefundStatus = order.latest_refund_status;
  const hasRefundHistory = refunds.length > 0 || order.refunds_count > 0;
  const entrySummary =
    validTickets.length > 0
      ? t("profile.orders.usableSummary", { count: validTickets.length })
      : order.checked_in_tickets_count > 0
        ? t("profile.orders.usedSummary", { count: order.checked_in_tickets_count })
        : t("profile.orders.usableSummary", { count: validTickets.length });

  return (
    <div className="order-detail-page">
      <section className="panel order-detail-hero">
        <div className="order-detail-hero__poster" aria-hidden="true">
          {posterSource ? <img src={posterSource} alt="" /> : <span>{getInitials(movieTitle)}</span>}
        </div>

        <div className="order-detail-hero__main">
          <div className="order-detail-hero__eyebrow">
            <span className="page-eyebrow">
              {t("orderDetails.eyebrow", { defaultValue: "Order details" })}
            </span>
            <span className={`order-detail-validity ${validityClass}`}>
              {order.valid_for_entry
                ? t("orderDetails.validity.valid", { defaultValue: "Valid for entry" })
                : t("orderDetails.validity.invalid", { defaultValue: "Not valid for entry" })}
            </span>
          </div>

          <h1 className="page-title order-detail-hero__title">{movieTitle}</h1>
          <p className="page-subtitle">
            {formatDateTime(order.session_start_time, i18n.language)} | {formatStateLabel(order.session_status)}
          </p>

          <div className="order-detail-hero__badges">
            <span className="badge">{t("profile.orders.shortId", { id: shortOrderId })}</span>
            <span className="badge">{formatStateLabel(order.status)}</span>
            {order.age_rating ? <span className="badge">{order.age_rating}</span> : null}
            <span className="badge">{entrySummary}</span>
          </div>
        </div>

        <aside className="order-detail-hero__actions">
          {canContinueCheckout ? (
            <Link to={`/checkout/${order.id}`} className="button">
              {t("checkout.actions.continueCheckout")}
            </Link>
          ) : null}
          {canDownloadPdf ? (
            <button
              className={canContinueCheckout ? "button--ghost" : "button"}
              type="button"
              disabled={isDownloadingPdf}
              onClick={() => void handleDownloadPdf()}
            >
              {isDownloadingPdf
                ? t("orderDetails.pdf.loading", { defaultValue: "Preparing PDF..." })
                : t("common.actions.downloadPdf")}
            </button>
          ) : null}
          {order.full_refund_available ? (
            <button
              className="button--ghost"
              type="button"
              disabled={refundingTarget === "order"}
              onClick={() => void handleFullRefund()}
            >
              {refundingTarget === "order"
                ? t("orderDetails.refunds.requesting", { defaultValue: "Requesting..." })
                : t("orderDetails.refunds.fullAction", { defaultValue: "Request full refund" })}
            </button>
          ) : null}
          <Link to={`/schedule/${order.session_id}`} className="button--ghost">
            {t("common.actions.viewSession")}
          </Link>
          <Link to="/profile" className="button--ghost">
            {t("orderDetails.actions.backToOrders", { defaultValue: "Back to my orders" })}
          </Link>
        </aside>
      </section>

      {feedback ? <StatusBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}

      {canContinueCheckout ? (
        <StatusBanner
          tone="info"
          title={t("checkout.status.reserved.title")}
          message={t("checkout.status.reserved.message", {
            expiresAt: order.expires_at
              ? formatDateTime(order.expires_at, i18n.language)
              : t("checkout.labels.notApplicable"),
          })}
          action={
            <Link to={`/checkout/${order.id}`} className="button">
              {t("checkout.actions.continueCheckout")}
            </Link>
          }
        />
      ) : null}

      <section className="order-detail-layout">
        <section className="order-detail-main">
          <article className="panel order-detail-summary">
            <div className="order-detail-section-head">
              <div>
                <h2 className="section-title">
                  {t("orderDetails.summary.title", { defaultValue: "Order summary" })}
                </h2>
                <p className="muted">
                  {t("orderDetails.summary.intro", {
                    defaultValue: "Receipt-level information for this grouped purchase.",
                  })}
                </p>
              </div>
            </div>

            <div className="order-detail-facts">
              <div className="order-detail-fact">
                <span>{t("orderDetails.summary.orderId", { defaultValue: "Order id" })}</span>
                <strong title={order.id}>{order.id}</strong>
              </div>
              <div className="order-detail-fact">
                <span>{t("common.labels.status")}</span>
                <strong>{formatStateLabel(order.status)}</strong>
              </div>
              <div className="order-detail-fact">
                <span>{t("common.labels.date")}</span>
                <strong>{formatDateTime(order.created_at, i18n.language)}</strong>
              </div>
              <div className="order-detail-fact">
                <span>{t("common.labels.total")}</span>
                <strong>{formatCurrency(order.total_price, i18n.language)}</strong>
              </div>
              <div className="order-detail-fact">
                <span>{t("common.labels.tickets")}</span>
                <strong>{order.tickets_count}</strong>
              </div>
              <div className="order-detail-fact">
                <span>{t("orderDetails.summary.activeCancelled", { defaultValue: "Active / cancelled" })}</span>
                <strong>
                  {order.active_tickets_count} / {order.cancelled_tickets_count}
                </strong>
              </div>
              <div className="order-detail-fact">
                <span>{t("orderDetails.summary.checkedIn", { defaultValue: "Checked in" })}</span>
                <strong>
                  {order.checked_in_tickets_count} / {order.active_tickets_count}
                </strong>
              </div>
            </div>
          </article>

          <article className="panel order-detail-tickets">
            <div className="order-detail-section-head">
              <div>
                <h2 className="section-title">
                  {t("orderDetails.tickets.title", { defaultValue: "Tickets" })}
                </h2>
                <p className="muted">
                  {t("orderDetails.tickets.intro", {
                    defaultValue: "Each seat keeps its own cancellation and entry-validity state.",
                  })}
                </p>
              </div>
              <span className="badge">
                {validTickets.length} {t("orderDetails.tickets.validCount", { defaultValue: "valid" })}
              </span>
            </div>

            <div className="order-detail-ticket-list">
              {order.tickets.map((ticket) => {
                const ticketTimeline = formatTicketTimeline(ticket, order.created_at, t, i18n.language);
                return (
                  <article
                    key={ticket.id}
                    className={`order-detail-ticket ${ticket.valid_for_entry ? "is-valid" : "is-invalid"}`}
                  >
                  <div className="order-detail-ticket__seat">
                    <span>{t("common.labels.seat")}</span>
                    <strong>
                      {ticket.seat_row}-{ticket.seat_number}
                    </strong>
                  </div>

                  <div className="order-detail-ticket__body">
                    <div className="order-detail-ticket__topline">
                      <strong>
                        {t("orderDetails.tickets.rowSeat", {
                          defaultValue: "Row {{row}}, seat {{seat}}",
                          row: ticket.seat_row,
                          seat: ticket.seat_number,
                        })}
                      </strong>
                      <span className="badge">{formatStateLabel(ticket.status)}</span>
                    </div>
                    <p className="muted">
                      {ticketTimeline}
                    </p>
                  </div>

                  <div className="order-detail-ticket__meta">
                    <span className={`order-detail-validity ${ticket.valid_for_entry ? "is-valid" : "is-invalid"}`}>
                      {ticket.valid_for_entry
                        ? t("orderDetails.validity.ticketValid", { defaultValue: "Entry valid" })
                        : t("orderDetails.validity.ticketInvalid", { defaultValue: "Entry not valid" })}
                    </span>
                    <span className="badge">{formatCurrency(ticket.price, i18n.language)}</span>
                    {ticket.refund_status ? (
                      <span className={`badge order-detail-refund-badge order-detail-refund-badge--${ticket.refund_status}`}>
                        {getRefundStatusLabel(ticket.refund_status, t)}
                      </span>
                    ) : null}
                    {ticket.is_cancellable ? (
                      <button
                        className="button--ghost order-detail-ticket__cancel"
                        type="button"
                        disabled={cancellingTicketId === ticket.id}
                        onClick={() => void handleCancelTicket(ticket)}
                      >
                        {cancellingTicketId === ticket.id
                          ? t("profile.orders.cancelLoading")
                          : t("common.actions.cancelTicket")}
                      </button>
                    ) : null}
                    {ticket.is_refundable ? (
                      <button
                        className="button--ghost order-detail-ticket__refund"
                        type="button"
                        disabled={refundingTarget === `ticket:${ticket.id}`}
                        onClick={() => void handleTicketRefund(ticket)}
                      >
                        {refundingTarget === `ticket:${ticket.id}`
                          ? t("orderDetails.refunds.requesting", { defaultValue: "Requesting..." })
                          : t("orderDetails.refunds.ticketAction", { defaultValue: "Request refund" })}
                      </button>
                    ) : null}
                  </div>
                  </article>
                );
              })}
            </div>
          </article>
        </section>

        <aside className="order-detail-side">
          <article className="panel order-detail-refunds">
            <div className="order-detail-section-head">
              <div>
                <h2 className="section-title">
                  {t("orderDetails.refunds.title", { defaultValue: "Refunds" })}
                </h2>
                <p className="muted">
                  {order.full_refund_available
                    ? t("orderDetails.refunds.fullAvailable", {
                        defaultValue: "This cancelled order has refundable payment balance.",
                      })
                    : hasRefundHistory
                      ? t("orderDetails.refunds.historyIntro", {
                          defaultValue: "Refund activity for this order payment.",
                        })
                      : t("orderDetails.refunds.noneIntro", {
                          defaultValue: "Refund actions appear after paid tickets are cancelled.",
                        })}
                </p>
              </div>
              {latestRefundStatus ? (
                <span className={`badge order-detail-refund-badge order-detail-refund-badge--${latestRefundStatus}`}>
                  {getRefundStatusLabel(latestRefundStatus, t)}
                </span>
              ) : null}
            </div>

            <div className="order-detail-side-list">
              <div>
                <span>{t("orderDetails.refunds.refunded", { defaultValue: "Refunded" })}</span>
                <strong>{formatMinorAmount(refundedAmount, refundCurrency, i18n.language)}</strong>
              </div>
              <div>
                <span>{t("orderDetails.refunds.remaining", { defaultValue: "Remaining refundable" })}</span>
                <strong>{formatMinorAmount(remainingRefundableAmount, refundCurrency, i18n.language)}</strong>
              </div>
              <div>
                <span>{t("orderDetails.refunds.count", { defaultValue: "Refund records" })}</span>
                <strong>{order.refunds_count}</strong>
              </div>
            </div>

            {order.full_refund_available ? (
              <button
                className="button order-detail-refunds__action"
                type="button"
                disabled={refundingTarget === "order"}
                onClick={() => void handleFullRefund()}
              >
                {refundingTarget === "order"
                  ? t("orderDetails.refunds.requesting", { defaultValue: "Requesting..." })
                  : t("orderDetails.refunds.fullAction", { defaultValue: "Request full refund" })}
              </button>
            ) : null}
          </article>

          <article className={`panel order-detail-entry ${validityClass}`}>
            <span className="page-eyebrow">
              {t("orderDetails.validation.title", { defaultValue: "Entry validation" })}
            </span>
            <h2 className="section-title">
              {order.valid_for_entry
                ? t("orderDetails.validation.readyTitle", { defaultValue: "Ready for staff scan" })
                : t("orderDetails.validation.blockedTitle", { defaultValue: "Entry is blocked" })}
            </h2>
            <p>{order.entry_status_message}</p>
            <div className="order-detail-entry__code">
              <span>{t("orderDetails.validation.code", { defaultValue: "Validation code" })}</span>
              <strong>{formatStateLabel(order.entry_status_code)}</strong>
            </div>
          </article>

          <article className="panel order-detail-session">
            <h2 className="section-title">
              {t("orderDetails.session.title", { defaultValue: "Session" })}
            </h2>
            <div className="order-detail-side-list">
              <div>
                <span>{t("common.labels.movie")}</span>
                <strong>{movieTitle}</strong>
              </div>
              <div>
                <span>{t("common.labels.startsAt")}</span>
                <strong>{formatDateTime(order.session_start_time, i18n.language)}</strong>
              </div>
              <div>
                <span>{t("common.labels.endsAt")}</span>
                <strong>{formatDateTime(order.session_end_time, i18n.language)}</strong>
              </div>
              <div>
                <span>{t("common.labels.status")}</span>
                <strong>{formatStateLabel(order.session_status)}</strong>
              </div>
              <div>
                <span>{t("common.labels.pricePerTicket")}</span>
                <strong>{formatCurrency(order.session_price, i18n.language)}</strong>
              </div>
              <div>
                <span>{t("orderDetails.session.hall", { defaultValue: "Hall" })}</span>
                <strong>{t("orderDetails.session.hallName", { defaultValue: "Hall 1" })}</strong>
              </div>
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
