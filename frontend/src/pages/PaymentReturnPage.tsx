import axios from "axios";
import type { TFunction } from "i18next";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import "./CheckoutPage.css";

import { getMyOrderRequest } from "@/api/orders";
import {
  getOrderPaymentDetailsRequest,
  getPaymentDetailsRequest,
  retryOrderPaymentRequest,
  type PaymentInitiationPayload,
} from "@/api/payments";
import { extractApiErrorMessage } from "@/shared/apiErrors";
import { getLocalizedText } from "@/shared/localization";
import {
  canRetryPayment,
  hasActivePayment,
  isPaidOrder,
  isReleasedOrder,
  resolvePaymentRedirectUrl,
} from "@/shared/payment";
import { formatCurrency, formatDateTime, formatStateLabel } from "@/shared/presentation";
import { StatePanel } from "@/shared/ui/StatePanel";
import { StatusBanner } from "@/shared/ui/StatusBanner";
import type { OrderDetails, PaymentDetails, PaymentInitiation } from "@/types/domain";

type BannerTone = "info" | "success" | "error" | "warning";

const RETURN_POLL_INTERVAL_MS = 4000;
const RETURN_POLL_LIMIT = 5;

function isMissingPaymentError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

function buildIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `return-retry-${crypto.randomUUID()}`;
  }
  return `return-retry-${Date.now()}-${Math.random().toString(16).slice(2)}`;
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

function getReturnStatus(
  order: OrderDetails,
  payment: PaymentDetails | null,
  t: TFunction,
): { tone: BannerTone; title: string; message: string } {
  if (isPaidOrder(order)) {
    return {
      tone: "success",
      title: t("checkout.return.status.paidTitle"),
      message: t("checkout.return.status.paidMessage"),
    };
  }
  if (order.status === "payment_failed" || payment?.status === "failed") {
    return {
      tone: "error",
      title: t("checkout.return.status.failedTitle"),
      message: t("checkout.return.status.failedMessage"),
    };
  }
  if (order.status === "payment_cancelled" || payment?.status === "cancelled") {
    return {
      tone: "warning",
      title: t("checkout.return.status.cancelledTitle"),
      message: t("checkout.return.status.cancelledMessage"),
    };
  }
  if (order.status === "expired" || payment?.status === "expired") {
    return {
      tone: "warning",
      title: t("checkout.return.status.expiredTitle"),
      message: t("checkout.return.status.expiredMessage"),
    };
  }
  return {
    tone: "info",
    title: t("checkout.return.status.pendingTitle"),
    message: t("checkout.return.status.pendingMessage"),
  };
}

export function PaymentReturnPage() {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const orderIdParam = searchParams.get("orderId") ?? "";
  const paymentIdParam = searchParams.get("paymentId") ?? "";
  const [order, setOrder] = useState<OrderDetails | null>(null);
  const [payment, setPayment] = useState<PaymentDetails | null>(null);
  const [lastInitiation, setLastInitiation] = useState<PaymentInitiation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [feedback, setFeedback] = useState<{
    tone: BannerTone;
    title?: string;
    message: string;
  } | null>(null);

  const loadReturnState = useCallback(
    async (options?: { background?: boolean }) => {
      const background = options?.background ?? false;
      if (background) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
        setErrorMessage("");
      }

      try {
        let resolvedOrderId = orderIdParam;
        let resolvedPayment: PaymentDetails | null = null;

        if (!resolvedOrderId && paymentIdParam) {
          const paymentResponse = await getPaymentDetailsRequest(paymentIdParam);
          resolvedPayment = paymentResponse.data;
          resolvedOrderId = paymentResponse.data.order_id;
        }

        if (!resolvedOrderId) {
          throw new Error(t("checkout.return.errors.missingContext"));
        }

        const orderResponse = await getMyOrderRequest(resolvedOrderId);
        setOrder(orderResponse.data);

        try {
          if (!resolvedPayment) {
            const paymentResponse = await getOrderPaymentDetailsRequest(resolvedOrderId);
            resolvedPayment = paymentResponse.data;
          }
          setPayment(resolvedPayment);
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
        setErrorMessage(extractApiErrorMessage(error, t("checkout.return.errors.unavailable")));
      } finally {
        if (background) {
          setIsRefreshing(false);
        } else {
          setIsLoading(false);
        }
      }
    },
    [orderIdParam, paymentIdParam, t],
  );

  useEffect(() => {
    setFeedback(null);
    setLastInitiation(null);
    void loadReturnState();
  }, [loadReturnState]);

  useEffect(() => {
    if (!order || !payment || !hasActivePayment(payment) || isPaidOrder(order) || isReleasedOrder(order)) {
      return;
    }

    let refreshCount = 0;
    const timer = window.setInterval(() => {
      refreshCount += 1;
      void loadReturnState({ background: true });
      if (refreshCount >= RETURN_POLL_LIMIT) {
        window.clearInterval(timer);
      }
    }, RETURN_POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [loadReturnState, order, payment]);

  async function handleRetry() {
    if (!order || isRetrying) {
      return;
    }

    const payload: PaymentInitiationPayload = {
      idempotency_key: buildIdempotencyKey(),
      ...buildPaymentUrls(order.id),
      metadata: {
        source: "payment_return_retry",
      },
    };

    setIsRetrying(true);
    setFeedback(null);
    try {
      const response = await retryOrderPaymentRequest(order.id, payload);
      setLastInitiation(response.data);
      const redirectUrl = resolvePaymentRedirectUrl(response.data);
      if (redirectUrl) {
        window.location.assign(redirectUrl);
        return;
      }
      await loadReturnState({ background: true });
      setFeedback({
        tone: "info",
        title: t("checkout.feedback.statusUpdatedTitle"),
        message: t("checkout.feedback.statusUpdatedMessage"),
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        title: t("checkout.feedback.retryFailedTitle"),
        message: extractApiErrorMessage(error, t("checkout.errors.retryFailed")),
      });
      await loadReturnState({ background: true });
    } finally {
      setIsRetrying(false);
    }
  }

  if (isLoading) {
    return (
      <StatePanel
        tone="loading"
        title={t("checkout.return.loading.title")}
        message={t("checkout.return.loading.message")}
      />
    );
  }

  if (errorMessage || !order) {
    return (
      <StatePanel
        tone="error"
        title={t("checkout.return.errors.title")}
        message={errorMessage || t("checkout.return.errors.unavailable")}
        action={
          <>
            <button className="button--ghost" type="button" onClick={() => void loadReturnState()}>
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

  const movieTitle = getLocalizedText(order.movie_title, i18n.language);
  const status = getReturnStatus(order, payment, t);
  const retryAllowed = canRetryPayment(order, payment);
  const activeRedirectUrl =
    payment &&
    lastInitiation?.payment_id === payment.id &&
    hasActivePayment(payment)
      ? resolvePaymentRedirectUrl(lastInitiation)
      : null;

  return (
    <div className="checkout-page checkout-return-page">
      <section className={`panel checkout-return checkout-return--${status.tone}`}>
        <div className="checkout-return__copy">
          <p className="page-eyebrow">{t("checkout.return.eyebrow")}</p>
          <h1 className="page-title">{status.title}</h1>
          <p className="page-subtitle">{status.message}</p>
        </div>

        <div className="checkout-return__facts">
          <div className="checkout-fact">
            <span>{t("common.labels.movie")}</span>
            <strong>{movieTitle}</strong>
          </div>
          <div className="checkout-fact">
            <span>{t("profile.orders.shortId", { id: order.id.slice(-8).toUpperCase() })}</span>
            <strong>{formatStateLabel(order.status)}</strong>
          </div>
          <div className="checkout-fact">
            <span>{t("checkout.labels.paymentStatus")}</span>
            <strong>{payment ? formatStateLabel(payment.status) : t("checkout.labels.notStarted")}</strong>
          </div>
          <div className="checkout-fact">
            <span>{t("common.labels.total")}</span>
            <strong>{formatCurrency(order.total_price, i18n.language)}</strong>
          </div>
        </div>
      </section>

      {feedback ? <StatusBanner tone={feedback.tone} title={feedback.title} message={feedback.message} /> : null}

      <section className="panel checkout-return-actions">
        <div className="checkout-section-head">
          <div>
            <h2 className="section-title">{t("checkout.return.nextStepsTitle")}</h2>
            <p className="muted">{t("checkout.return.nextStepsIntro")}</p>
          </div>
          {isRefreshing ? <span className="badge">{t("checkout.labels.refreshing")}</span> : null}
        </div>

        <div className="actions-row">
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

          {retryAllowed ? (
            <button className="button" type="button" disabled={isRetrying || isRefreshing} onClick={() => void handleRetry()}>
              {isRetrying ? t("checkout.actions.preparingPayment") : t("checkout.actions.retryPayment")}
            </button>
          ) : null}

          {isPaidOrder(order) ? (
            <Link to={`/me/orders/${order.id}`} className="button">
              {t("checkout.actions.viewPaidOrder")}
            </Link>
          ) : (
            <Link to={`/checkout/${order.id}`} className="button--ghost">
              {t("checkout.actions.backToCheckout")}
            </Link>
          )}

          <button
            className="button--ghost"
            type="button"
            disabled={isRefreshing || isRetrying}
            onClick={() => void loadReturnState({ background: true })}
          >
            {isRefreshing ? t("checkout.labels.refreshing") : t("checkout.actions.refreshStatus")}
          </button>

          <Link to="/profile" className="button--ghost">
            {t("checkout.actions.backToOrders")}
          </Link>
        </div>
      </section>
    </div>
  );
}
