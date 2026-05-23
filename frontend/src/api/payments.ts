import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/types/api";
import type { PaymentDetails, PaymentInitiation } from "@/types/domain";

export interface PaymentInitiationPayload {
  idempotency_key?: string;
  return_url?: string;
  cancel_url?: string;
  metadata?: Record<string, unknown>;
}

function paymentHeaders(payload: PaymentInitiationPayload) {
  return payload.idempotency_key
    ? {
        "Idempotency-Key": payload.idempotency_key,
      }
    : undefined;
}

export async function initiateOrderPaymentRequest(
  orderId: string,
  payload: PaymentInitiationPayload,
) {
  const { data } = await apiClient.post<ApiResponse<PaymentInitiation>>(
    `/orders/${orderId}/payments`,
    payload,
    {
      headers: paymentHeaders(payload),
    },
  );
  return data;
}

export async function retryOrderPaymentRequest(
  orderId: string,
  payload: PaymentInitiationPayload,
) {
  const { data } = await apiClient.post<ApiResponse<PaymentInitiation>>(
    `/orders/${orderId}/payments/retry`,
    payload,
    {
      headers: paymentHeaders(payload),
    },
  );
  return data;
}

export async function getOrderPaymentDetailsRequest(orderId: string) {
  const { data } = await apiClient.get<ApiResponse<PaymentDetails>>(`/orders/${orderId}/payment`);
  return data;
}

export async function getPaymentDetailsRequest(paymentId: string) {
  const { data } = await apiClient.get<ApiResponse<PaymentDetails>>(`/payments/${paymentId}`);
  return data;
}
