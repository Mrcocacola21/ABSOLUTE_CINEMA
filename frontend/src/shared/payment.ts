import type { Order, PaymentDetails, PaymentInitiation, PaymentStatus } from "@/types/domain";

export const ACTIVE_PAYMENT_STATUSES: PaymentStatus[] = [
  "created",
  "pending",
  "requires_action",
];

export const RETRYABLE_PAYMENT_STATUSES: PaymentStatus[] = [
  "failed",
  "cancelled",
  "expired",
];

export function isPaidOrder(order: Order): boolean {
  return order.status === "completed" || order.status === "partially_cancelled";
}

export function isPendingPaymentOrder(order: Order): boolean {
  return order.status === "pending_payment";
}

export function isReleasedOrder(order: Order): boolean {
  return ["payment_failed", "payment_cancelled", "cancelled", "expired"].includes(order.status);
}

export function isReservationPastDue(order: Order, now: Date = new Date()): boolean {
  return Boolean(order.expires_at && new Date(order.expires_at).getTime() <= now.getTime());
}

export function hasActivePayment(payment: PaymentDetails | null): boolean {
  return Boolean(payment && ACTIVE_PAYMENT_STATUSES.includes(payment.status));
}

export function hasRetryablePayment(payment: PaymentDetails | null): boolean {
  return Boolean(payment && RETRYABLE_PAYMENT_STATUSES.includes(payment.status));
}

export function canRetryPayment(order: Order, payment: PaymentDetails | null): boolean {
  return isPendingPaymentOrder(order) && !isReservationPastDue(order) && hasRetryablePayment(payment);
}

export function canInitiatePayment(order: Order, payment: PaymentDetails | null): boolean {
  if (!isPendingPaymentOrder(order) || isReservationPastDue(order)) {
    return false;
  }
  return !payment || hasActivePayment(payment);
}

export function resolvePaymentRedirectUrl(initiation: PaymentInitiation | null): string | null {
  if (!initiation) {
    return null;
  }
  if (initiation.provider === "fake" && typeof window !== "undefined") {
    const url = new URL(`/payment/fake/${initiation.payment_id}`, window.location.origin);
    url.searchParams.set("orderId", initiation.order_id);
    return url.toString();
  }
  return initiation.redirect_url ?? null;
}
