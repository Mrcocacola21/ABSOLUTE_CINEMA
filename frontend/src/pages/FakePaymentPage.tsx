import axios from "axios";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import "./FakePaymentPage.css";

import { getMyOrderRequest } from "@/api/orders";
import {
  getPaymentDetailsRequest,
  simulateFakeProviderPaymentRequest,
} from "@/api/payments";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getLocalizedText } from "@/shared/localization";
import {
  hasActivePayment,
  isPendingPaymentOrder,
  isReservationPastDue,
} from "@/shared/payment";
import { resolvePosterSource } from "@/shared/posters";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type {
  OrderDetails,
  PaymentDetails,
  PaymentSimulationResult,
} from "@/types/domain";

type BannerTone = "info" | "success" | "error" | "warning";

interface ProviderAction {
  result: PaymentSimulationResult;
  label: string;
  detail: string;
  tone: BannerTone;
}

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

function isMissingOrderError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

function buildReturnUrl(orderId: string, paymentId: string, result?: PaymentSimulationResult) {
  const url = new URL("/payment/return", window.location.origin);
  url.searchParams.set("orderId", orderId);
  url.searchParams.set("paymentId", paymentId);
  if (result) {
    url.searchParams.set("result", result);
  }
  return `${url.pathname}${url.search}`;
}

function getProviderStatus(
  order: OrderDetails | null,
  payment: PaymentDetails | null,
): { tone: BannerTone; label: string } {
  if (order?.status === "completed" || order?.status === "partially_cancelled") {
    return { tone: "success", label: "Payment complete" };
  }
  if (order?.status === "payment_failed" || payment?.status === "failed") {
    return { tone: "error", label: "Payment failed" };
  }
  if (order?.status === "payment_cancelled" || payment?.status === "cancelled") {
    return { tone: "warning", label: "Payment cancelled" };
  }
  if (order?.status === "expired" || payment?.status === "expired") {
    return { tone: "warning", label: "Reservation expired" };
  }
  if (payment?.status === "requires_action") {
    return { tone: "warning", label: "Action required" };
  }
  return { tone: "info", label: "Awaiting provider result" };
}

export function FakePaymentPage() {
  const { paymentId = "" } = useParams<{ paymentId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [order, setOrder] = useState<OrderDetails | null>(null);
  const [payment, setPayment] = useState<PaymentDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeResult, setActiveResult] = useState<PaymentSimulationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: BannerTone;
    title?: string;
    message: string;
  } | null>(null);

  const loadProviderState = useCallback(async () => {
    if (!paymentId) {
      setErrorMessage(t("fakePayment.errors.missingPayment", { defaultValue: "Payment id is missing." }));
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setErrorMessage("");

    try {
      const paymentResponse = await getPaymentDetailsRequest(paymentId);
      const loadedPayment = paymentResponse.data;
      setPayment(loadedPayment);

      const queryOrderId = searchParams.get("orderId") ?? "";
      const resolvedOrderId = queryOrderId || loadedPayment.order_id;
      try {
        const orderResponse = await getMyOrderRequest(resolvedOrderId);
        setOrder(orderResponse.data);
      } catch (orderError) {
        if (isMissingOrderError(orderError)) {
          setOrder(null);
        } else {
          throw orderError;
        }
      }
    } catch (error) {
      setPayment(null);
      setOrder(null);
      setErrorMessage(
        extractApiErrorMessage(
          error,
          t("fakePayment.errors.unavailable", {
            defaultValue: "The fake payment page could not load this payment.",
          }),
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, [paymentId, searchParams, t]);

  useEffect(() => {
    setFeedback(null);
    void loadProviderState();
  }, [loadProviderState]);

  const movieTitle = order ? getLocalizedText(order.movie_title, i18n.language) : "Cinema order";
  const posterSource = order ? resolvePosterSource(order) : null;
  const status = getProviderStatus(order, payment);
  const seats = useMemo(
    () =>
      order?.tickets
        .map((ticket) => `${ticket.seat_row}-${ticket.seat_number}`)
        .join(", ") ?? "",
    [order],
  );
  const canSimulate =
    Boolean(payment && hasActivePayment(payment)) &&
    Boolean(order && isPendingPaymentOrder(order) && !isReservationPastDue(order));
  const returnPath = payment
    ? buildReturnUrl(order?.id ?? payment.order_id, payment.id)
    : "/profile";

  const actions: ProviderAction[] = [
    {
      result: "succeeded",
      label: t("fakePayment.actions.success", { defaultValue: "Successful payment" }),
      detail: t("fakePayment.actions.successDetail", { defaultValue: "Mark provider payment as paid" }),
      tone: "success",
    },
    {
      result: "failed",
      label: t("fakePayment.actions.failed", { defaultValue: "Payment failed" }),
      detail: t("fakePayment.actions.failedDetail", { defaultValue: "Return a provider decline" }),
      tone: "error",
    },
    {
      result: "cancelled",
      label: t("fakePayment.actions.cancelled", { defaultValue: "Cancel payment" }),
      detail: t("fakePayment.actions.cancelledDetail", { defaultValue: "Return a provider cancellation" }),
      tone: "warning",
    },
    {
      result: "pending",
      label: t("fakePayment.actions.pending", { defaultValue: "Leave pending" }),
      detail: t("fakePayment.actions.pendingDetail", { defaultValue: "Keep the payment unresolved" }),
      tone: "info",
    },
  ];

  async function handleSimulation(result: PaymentSimulationResult) {
    if (!payment || !order || activeResult) {
      return;
    }

    setActiveResult(result);
    setFeedback(null);
    try {
      const response = await simulateFakeProviderPaymentRequest(payment.id, result);
      setPayment(response.data.payment);
      navigate(buildReturnUrl(order.id, payment.id, result), { replace: true });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("fakePayment.errors.actionTitle", { defaultValue: "Provider action failed" }),
        message: extractApiErrorMessage(
          error,
          t("fakePayment.errors.actionMessage", {
            defaultValue: "The backend did not accept this fake-provider result.",
          }),
        ),
      });
      await loadProviderState();
    } finally {
      setActiveResult(null);
    }
  }

  if (isLoading) {
    return (
      <StatePanel
        tone="loading"
        title={t("fakePayment.loading.title", { defaultValue: "Loading fake provider" })}
        message={t("fakePayment.loading.message", {
          defaultValue: "Fetching the payment, order, and reservation state.",
        })}
      />
    );
  }

  if (errorMessage || !payment) {
    return (
      <StatePanel
        tone="error"
        title={t("fakePayment.errors.title", { defaultValue: "Unable to open fake provider" })}
        message={errorMessage}
        action={
          <div className="actions-row">
            <button className="button--ghost" type="button" onClick={() => void loadProviderState()}>
              {t("common.actions.retry")}
            </button>
            <Link to="/profile" className="button">
              {t("checkout.actions.backToOrders")}
            </Link>
          </div>
        }
      />
    );
  }

  return (
    <div className="fake-payment-page">
      <section className={`panel fake-payment-hero fake-payment-hero--${status.tone}`}>
        <div className="fake-payment-hero__poster" aria-hidden="true">
          {posterSource ? <img src={posterSource} alt="" /> : <span>{getInitials(movieTitle)}</span>}
        </div>

        <div className="fake-payment-hero__copy">
          <p className="page-eyebrow">
            {t("fakePayment.eyebrow", { defaultValue: "Local fake provider" })}
          </p>
          <h1 className="page-title fake-payment-hero__title">{movieTitle}</h1>
          <p className="page-subtitle">
            {order
              ? `${formatDateTime(order.session_start_time, i18n.language)} | ${formatStateLabel(order.session_status)}`
              : t("fakePayment.orderUnavailable", { defaultValue: "Order details unavailable" })}
          </p>

          <div className="fake-payment-hero__badges">
            <span className="badge">{formatStateLabel(payment.status)}</span>
            {order ? <span className="badge">{formatStateLabel(order.status)}</span> : null}
            <span className="badge">
              {order
                ? formatCurrency(order.total_price, i18n.language)
                : `${payment.amount_minor / 100} ${payment.currency}`}
            </span>
          </div>
        </div>

        <aside className="fake-payment-hero__status">
          <span className="page-eyebrow">
            {t("checkout.labels.currentStatus", { defaultValue: "Current status" })}
          </span>
          <h2 className="section-title">{status.label}</h2>
          <p>
            {t("fakePayment.statusCopy", {
              defaultValue: "Provider result will be confirmed by the backend payment lifecycle.",
            })}
          </p>
        </aside>
      </section>

      {feedback ? <StatusBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}

      {!canSimulate ? (
        <StatusBanner
          tone="warning"
          title={t("fakePayment.locked.title", { defaultValue: "Payment is no longer actionable" })}
          message={t("fakePayment.locked.message", {
            defaultValue: "Return to the app to inspect the latest order and payment state.",
          })}
          action={
            <Link to={returnPath} className="button">
              {t("fakePayment.actions.returnToApp", { defaultValue: "Return to app" })}
            </Link>
          }
        />
      ) : null}

      <section className="fake-payment-layout">
        <article className="panel fake-payment-actions-panel">
          <div className="fake-payment-section-head">
            <div>
              <h2 className="section-title">
                {t("fakePayment.actionsTitle", { defaultValue: "Provider result" })}
              </h2>
              <p className="muted">
                {t("fakePayment.actionsIntro", {
                  defaultValue: "Select the outcome to send for this local fake-provider payment.",
                })}
              </p>
            </div>
            <span className="badge">{payment.provider}</span>
          </div>

          <div className="fake-payment-action-grid">
            {actions.map((action) => (
              <button
                key={action.result}
                className={`fake-payment-action fake-payment-action--${action.tone}`}
                type="button"
                disabled={!canSimulate || activeResult !== null}
                onClick={() => void handleSimulation(action.result)}
              >
                <span>{activeResult === action.result ? t("checkout.actions.preparingPayment") : action.label}</span>
                <strong>{action.detail}</strong>
              </button>
            ))}
          </div>

          <div className="actions-row fake-payment-actions-panel__footer">
            <button
              className="button--ghost"
              type="button"
              disabled={activeResult !== null}
              onClick={() => void loadProviderState()}
            >
              {t("checkout.actions.refreshStatus", { defaultValue: "Refresh status" })}
            </button>
            <Link to={returnPath} className="button--ghost">
              {t("fakePayment.actions.returnWithoutAction", { defaultValue: "Return without action" })}
            </Link>
          </div>
        </article>

        <aside className="panel fake-payment-summary">
          <div className="fake-payment-section-head">
            <div>
              <h2 className="section-title">
                {t("checkout.summary.title", { defaultValue: "Reservation summary" })}
              </h2>
              <p className="muted">
                {t("fakePayment.summaryIntro", {
                  defaultValue: "Current backend state for the linked checkout.",
                })}
              </p>
            </div>
          </div>

          <div className="fake-payment-facts">
            <div>
              <span>{t("common.labels.selectedSeats", { defaultValue: "Selected seats" })}</span>
              <strong>{seats || t("checkout.labels.notApplicable", { defaultValue: "Not applicable" })}</strong>
            </div>
            <div>
              <span>{t("common.labels.total", { defaultValue: "Total" })}</span>
              <strong>
                {order
                  ? formatCurrency(order.total_price, i18n.language)
                  : `${payment.amount_minor / 100} ${payment.currency}`}
              </strong>
            </div>
            <div>
              <span>{t("checkout.labels.reservationExpires", { defaultValue: "Reservation expires" })}</span>
              <strong>
                {order?.expires_at
                  ? formatDateTime(order.expires_at, i18n.language)
                  : t("checkout.labels.notApplicable", { defaultValue: "Not applicable" })}
              </strong>
            </div>
            <div>
              <span>{t("checkout.labels.paymentProvider", { defaultValue: "Payment provider" })}</span>
              <strong>{payment.provider}</strong>
            </div>
          </div>

          <div className="fake-payment-technical">
            <h3>{t("fakePayment.technical.title", { defaultValue: "Technical" })}</h3>
            <dl>
              <div>
                <dt>{t("fakePayment.technical.paymentId", { defaultValue: "Payment id" })}</dt>
                <dd title={payment.id}>{payment.id}</dd>
              </div>
              <div>
                <dt>{t("fakePayment.technical.orderId", { defaultValue: "Order id" })}</dt>
                <dd title={order?.id ?? payment.order_id}>{order?.id ?? payment.order_id}</dd>
              </div>
              <div>
                <dt>{t("fakePayment.technical.providerReference", { defaultValue: "Provider reference" })}</dt>
                <dd title={payment.provider_payment_id ?? ""}>
                  {payment.provider_payment_id ?? t("checkout.labels.providerPending", { defaultValue: "Provider pending" })}
                </dd>
              </div>
            </dl>
          </div>
        </aside>
      </section>
    </div>
  );
}
