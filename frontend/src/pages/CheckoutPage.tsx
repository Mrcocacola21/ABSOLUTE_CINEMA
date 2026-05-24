import axios from "axios";
import type { TFunction } from "i18next";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import "./CheckoutPage.css";

import { getMyOrderRequest } from "@/api/orders";
import {
  getOrderPaymentDetailsRequest,
  initiateOrderPaymentRequest,
  retryOrderPaymentRequest,
  type PaymentInitiationPayload,
} from "@/api/payments";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getLocalizedText } from "@/shared/localization";
import {
  canInitiatePayment,
  canRetryPayment,
  hasActivePayment,
  isPaidOrder,
  isPendingPaymentOrder,
  isReleasedOrder,
  isReservationPastDue,
} from "@/shared/payment";
import { resolvePosterSource } from "@/shared/posters";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { OrderDetails, PaymentDetails, PaymentInitiation } from "@/types/domain";

type BannerTone = "info" | "success" | "error" | "warning";
type PaymentAction = "start" | "continue" | "retry";

const STATUS_POLL_INTERVAL_MS = 5000;
const STATUS_POLL_LIMIT = 6;

function getInitials(value: string): string {
  return (
    value
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join("") || "CS"
  );
}

function isMissingPaymentError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

function buildIdempotencyKey(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildPaymentUrls(orderId: string) {
  const returnUrl = new URL("/payment/return", window.location.origin);
  returnUrl.searchParams.set("orderId", orderId);

  const cancelUrl = new URL("/payment/return", window.location.origin);
  cancelUrl.searchParams.set("orderId", orderId);
  cancelUrl.searchParams.set("result", "cancelled");

  return {
    return_url: returnUrl.toString(),
    cancel_url: cancelUrl.toString(),
  };
}

function formatAttemptStatusLabel(status: string, t: TFunction): string {
  const defaultLabels: Record<string, string> = {
    created: "Provider attempt created",
    pending: "Provider handoff pending",
    succeeded: "Provider handoff ready",
    failed: "Provider handoff failed",
  };

  return t(`checkout.payment.attemptStatus.${status}`, {
    defaultValue: defaultLabels[status] ?? formatStateLabel(status),
  });
}

function getPrimaryPaymentAction(
  order: OrderDetails,
  payment: PaymentDetails | null,
): PaymentAction | null {
  if (canRetryPayment(order, payment)) {
    return "retry";
  }
  if (!canInitiatePayment(order, payment)) {
    return null;
  }
  return payment ? "continue" : "start";
}

function getCheckoutStatus(
  order: OrderDetails,
  payment: PaymentDetails | null,
  t: TFunction,
  language: string,
): { tone: BannerTone; title: string; message: string } {
  const expiresAt = order.expires_at ? formatDateTime(order.expires_at, language) : "";

  if (isPaidOrder(order)) {
    return {
      tone: "success",
      title: t("checkout.status.paid.title"),
      message: t("checkout.status.paid.message"),
    };
  }
  if (order.status === "expired") {
    return {
      tone: "warning",
      title: t("checkout.status.expired.title"),
      message: t("checkout.status.expired.message"),
    };
  }
  if (order.status === "payment_failed") {
    return {
      tone: "error",
      title: t("checkout.status.paymentFailed.title"),
      message: t("checkout.status.paymentFailed.message"),
    };
  }
  if (order.status === "payment_cancelled") {
    return {
      tone: "warning",
      title: t("checkout.status.paymentCancelled.title"),
      message: t("checkout.status.paymentCancelled.message"),
    };
  }
  if (order.status === "cancelled") {
    return {
      tone: "warning",
      title: t("checkout.status.cancelled.title"),
      message: t("checkout.status.cancelled.message"),
    };
  }
  if (isReservationPastDue(order)) {
    return {
      tone: "warning",
      title: t("checkout.status.expiring.title"),
      message: t("checkout.status.expiring.pastDueMessage"),
    };
  }
  if (!payment) {
    return {
      tone: "info",
      title: t("checkout.status.reserved.title"),
      message: t("checkout.status.reserved.message", { expiresAt }),
    };
  }
  if (payment.status === "requires_action") {
    return {
      tone: "warning",
      title: t("checkout.status.requiresAction.title"),
      message: t("checkout.status.requiresAction.message", { expiresAt }),
    };
  }
  if (payment.status === "succeeded" && isPendingPaymentOrder(order)) {
    return {
      tone: "info",
      title: t("checkout.status.processing.title"),
      message: t("checkout.status.processing.message"),
    };
  }
  if (payment.status === "failed") {
    return {
      tone: "error",
      title: t("checkout.status.failed.title"),
      message: t("checkout.status.failed.message", { expiresAt }),
    };
  }
  if (payment.status === "cancelled") {
    return {
      tone: "warning",
      title: t("checkout.status.cancelledPayment.title"),
      message: t("checkout.status.cancelledPayment.message", { expiresAt }),
    };
  }
  if (payment.status === "expired") {
    return {
      tone: "warning",
      title: t("checkout.status.paymentExpired.title"),
      message: t("checkout.status.paymentExpired.message", { expiresAt }),
    };
  }
  return {
    tone: "info",
    title: t("checkout.status.awaiting.title"),
    message: t("checkout.status.awaiting.message", { expiresAt }),
  };
}

export function CheckoutPage() {
  const { orderId = "" } = useParams<{ orderId: string }>();
  const { t, i18n } = useTranslation();
  const [order, setOrder] = useState<OrderDetails | null>(null);
  const [payment, setPayment] = useState<PaymentDetails | null>(null);
  const [lastInitiation, setLastInitiation] = useState<PaymentInitiation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: BannerTone;
    title?: string;
    message: string;
  } | null>(null);

  const loadCheckout = useCallback(
    async (options?: { background?: boolean }) => {
      if (!orderId) {
        setErrorMessage(t("checkout.errors.missingOrder"));
        setIsLoading(false);
        return;
      }

      const background = options?.background ?? false;
      if (background) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
        setErrorMessage("");
      }

      try {
        const orderResponse = await getMyOrderRequest(orderId);
        setOrder(orderResponse.data);

        try {
          const paymentResponse = await getOrderPaymentDetailsRequest(orderId);
          setPayment(paymentResponse.data);
        } catch (paymentError) {
          if (isMissingPaymentError(paymentError)) {
            setPayment(null);
          } else {
            throw paymentError;
          }
        }

        setErrorMessage("");
      } catch (error) {
        setOrder(null);
        setPayment(null);
        setLastInitiation(null);
        setErrorMessage(extractApiErrorMessage(error, t("checkout.errors.unavailable")));
      } finally {
        if (background) {
          setIsRefreshing(false);
        } else {
          setIsLoading(false);
        }
      }
    },
    [orderId, t],
  );

  useEffect(() => {
    setFeedback(null);
    setLastInitiation(null);
    void loadCheckout();
  }, [loadCheckout]);

  useEffect(() => {
    if (!order || !payment || !hasActivePayment(payment) || isPaidOrder(order) || isReleasedOrder(order)) {
      return;
    }

    let refreshCount = 0;
    const timer = window.setInterval(() => {
      refreshCount += 1;
      void loadCheckout({ background: true });
      if (refreshCount >= STATUS_POLL_LIMIT) {
        window.clearInterval(timer);
      }
    }, STATUS_POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [loadCheckout, order, payment]);

  const movieTitle = order ? getLocalizedText(order.movie_title, i18n.language) : "";
  const posterSource = order ? resolvePosterSource(order) : null;
  const status = order ? getCheckoutStatus(order, payment, t, i18n.language) : null;
  const primaryPaymentAction = order ? getPrimaryPaymentAction(order, payment) : null;
  const activeRedirectUrl =
    payment &&
    lastInitiation?.payment_id === payment.id &&
    hasActivePayment(payment) &&
    lastInitiation.redirect_url
      ? lastInitiation.redirect_url
      : null;
  const visiblePrimaryPaymentAction =
    activeRedirectUrl && primaryPaymentAction === "continue" ? null : primaryPaymentAction;

  const seatLabels = useMemo(
    () => order?.tickets.map((ticket) => `${ticket.seat_row}-${ticket.seat_number}`).join(", ") ?? "",
    [order],
  );

  async function handlePaymentAction(action: PaymentAction) {
    if (!order || isSubmitting) {
      return;
    }

    const idempotencyPrefix = action === "retry" ? "checkout-retry" : "checkout-init";
    const payload: PaymentInitiationPayload = {
      idempotency_key: buildIdempotencyKey(idempotencyPrefix),
      ...buildPaymentUrls(order.id),
      metadata: {
        source: action === "retry" ? "checkout_retry" : "checkout_page",
      },
    };

    setIsSubmitting(true);
    setFeedback(null);

    try {
      const response =
        action === "retry"
          ? await retryOrderPaymentRequest(order.id, payload)
          : await initiateOrderPaymentRequest(order.id, payload);
      setLastInitiation(response.data);
      await loadCheckout({ background: true });
      setFeedback({
        tone: response.data.redirect_url ? "success" : "info",
        title: response.data.redirect_url
          ? t("checkout.feedback.nextStepTitle")
          : t("checkout.feedback.statusUpdatedTitle"),
        message: response.data.redirect_url
          ? t("checkout.feedback.nextStepMessage")
          : t("checkout.feedback.statusUpdatedMessage"),
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title:
          action === "retry"
            ? t("checkout.feedback.retryFailedTitle")
            : t("checkout.feedback.initiationFailedTitle"),
        message: extractApiErrorMessage(error, t("checkout.errors.initiationFailed")),
      });
      await loadCheckout({ background: true });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <StatePanel
        tone="loading"
        title={t("checkout.loading.title")}
        message={t("checkout.loading.message")}
      />
    );
  }

  if (errorMessage || !order || !status) {
    return (
      <StatePanel
        tone="error"
        title={t("checkout.errors.title")}
        message={errorMessage || t("checkout.errors.unavailable")}
        action={
          <>
            <button className="button--ghost" type="button" onClick={() => void loadCheckout()}>
              {t("common.actions.retry")}
            </button>
            <Link to="/profile" className="button">
              {t("checkout.actions.backToOrders")}
            </Link>
          </>
        }
      />
    );
  }

  return (
    <div className="checkout-page">
      <section className={`panel checkout-hero checkout-hero--${status.tone}`}>
        <div className="checkout-hero__poster" aria-hidden="true">
          {posterSource ? <img src={posterSource} alt="" /> : <span>{getInitials(movieTitle)}</span>}
        </div>

        <div className="checkout-hero__copy">
          <p className="page-eyebrow">{t("checkout.page.eyebrow")}</p>
          <h1 className="page-title checkout-hero__title">{movieTitle}</h1>
          <p className="page-subtitle">
            {formatDateTime(order.session_start_time, i18n.language)} |{" "}
            {formatStateLabel(order.session_status)}
          </p>

          <div className="checkout-hero__badges">
            <span className="badge">{t("profile.orders.shortId", { id: order.id.slice(-8).toUpperCase() })}</span>
            <span className="badge">{formatStateLabel(order.status)}</span>
            {payment ? <span className="badge">{formatStateLabel(payment.status)}</span> : null}
            <span className="badge">{formatCurrency(order.total_price, i18n.language)}</span>
          </div>
        </div>

        <aside className="checkout-hero__status">
          <span className="page-eyebrow">{t("checkout.labels.currentStatus")}</span>
          <h2 className="section-title">{status.title}</h2>
          <p>{status.message}</p>
        </aside>
      </section>

      {feedback ? <StatusBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}

      <section className="checkout-layout">
        <article className="panel checkout-summary">
          <div className="checkout-section-head">
            <div>
              <h2 className="section-title">{t("checkout.summary.title")}</h2>
              <p className="muted">{t("checkout.summary.intro")}</p>
            </div>
            <Link to={`/me/orders/${order.id}`} className="button--ghost">
              {t("common.actions.viewDetails")}
            </Link>
          </div>

          <div className="checkout-facts">
            <div className="checkout-fact">
              <span>{t("common.labels.selectedSeats")}</span>
              <strong>{seatLabels}</strong>
            </div>
            <div className="checkout-fact">
              <span>{t("common.labels.tickets")}</span>
              <strong>{order.tickets_count}</strong>
            </div>
            <div className="checkout-fact">
              <span>{t("common.labels.pricePerTicket")}</span>
              <strong>{formatCurrency(order.session_price, i18n.language)}</strong>
            </div>
            <div className="checkout-fact">
              <span>{t("common.labels.total")}</span>
              <strong>{formatCurrency(order.total_price, i18n.language)}</strong>
            </div>
            <div className="checkout-fact">
              <span>{t("checkout.labels.reservationExpires")}</span>
              <strong>
                {order.expires_at
                  ? formatDateTime(order.expires_at, i18n.language)
                  : t("checkout.labels.notApplicable")}
              </strong>
            </div>
            <div className="checkout-fact">
              <span>{t("checkout.labels.ticketsValid")}</span>
              <strong>{order.valid_for_entry ? t("checkout.labels.yes") : t("checkout.labels.no")}</strong>
            </div>
          </div>

          <div className="checkout-seat-list" aria-label={t("common.labels.selectedSeats")}>
            {order.tickets.map((ticket) => (
              <span key={ticket.id} className={`checkout-seat-pill checkout-seat-pill--${ticket.status}`}>
                {t("common.labels.row")} {ticket.seat_row} | {t("common.labels.seat")} {ticket.seat_number}
              </span>
            ))}
          </div>

          <div className="actions-row checkout-summary__actions">
            <Link to={`/schedule/${order.session_id}`} className="button--ghost">
              {t("common.actions.backToSession")}
            </Link>
            <Link to="/profile" className="button--ghost">
              {t("checkout.actions.backToOrders")}
            </Link>
          </div>
        </article>

        <aside className="panel checkout-payment">
          <div className="checkout-section-head">
            <div>
              <h2 className="section-title">{t("checkout.payment.title")}</h2>
              <p className="muted">{t("checkout.payment.intro")}</p>
            </div>
            {isRefreshing ? <span className="badge">{t("checkout.labels.refreshing")}</span> : null}
          </div>

          <div className="checkout-payment__status-card">
            <span className={`checkout-payment__dot checkout-payment__dot--${status.tone}`} />
            <div>
              <strong>{status.title}</strong>
              <p>{status.message}</p>
            </div>
          </div>

          <div className="checkout-payment__details">
            <div>
              <span>{t("checkout.labels.paymentProvider")}</span>
              <strong>{payment?.provider ?? t("checkout.labels.providerPending")}</strong>
            </div>
            <div>
              <span>{t("common.labels.status")}</span>
              <strong>{payment ? formatStateLabel(payment.status) : t("checkout.labels.notStarted")}</strong>
            </div>
            <div>
              <span>{t("checkout.labels.attempts")}</span>
              <strong>{payment?.attempts.length ?? 0}</strong>
            </div>
          </div>

          {payment?.failure_message ? (
            <StatusBanner tone="error" message={payment.failure_message} />
          ) : null}

          <div className="checkout-payment__actions">
            {activeRedirectUrl ? (
              <button
                className="button"
                type="button"
                onClick={() => {
                  window.location.assign(activeRedirectUrl);
                }}
              >
                {t("checkout.actions.continueToProvider")}
              </button>
            ) : null}

            {visiblePrimaryPaymentAction ? (
              <button
                className={visiblePrimaryPaymentAction === "retry" ? "button--ghost" : "button"}
                type="button"
                disabled={isSubmitting || isRefreshing}
                onClick={() => void handlePaymentAction(visiblePrimaryPaymentAction)}
              >
                {isSubmitting
                  ? t("checkout.actions.preparingPayment")
                  : t(`checkout.actions.${visiblePrimaryPaymentAction}Payment`)}
              </button>
            ) : null}

            <button
              className="button--ghost"
              type="button"
              disabled={isRefreshing || isSubmitting}
              onClick={() => void loadCheckout({ background: true })}
            >
              {isRefreshing ? t("checkout.labels.refreshing") : t("checkout.actions.refreshStatus")}
            </button>
          </div>

          {payment?.attempts.length ? (
            <div className="checkout-attempts">
              <h3>{t("checkout.payment.attemptHistory")}</h3>
              <ol>
                {payment.attempts.slice(0, 4).map((attempt) => (
                  <li key={attempt.id}>
                    <span>{formatAttemptStatusLabel(attempt.status, t)}</span>
                    <strong>{formatDateTime(attempt.created_at, i18n.language)}</strong>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}

          {isPaidOrder(order) ? (
            <Link to={`/me/orders/${order.id}`} className="button checkout-payment__full-width">
              {t("checkout.actions.viewPaidOrder")}
            </Link>
          ) : null}
        </aside>
      </section>
    </div>
  );
}
