import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/types/api";
import type { Order } from "@/types/domain";

export interface OrderSeatPayload {
  seat_row: number;
  seat_number: number;
}

export interface PurchaseOrderPayload {
  session_id: string;
  seats: OrderSeatPayload[];
}

export async function purchaseOrderRequest(payload: PurchaseOrderPayload) {
  const { data } = await apiClient.post<ApiResponse<Order>>("/orders/purchase", payload);
  return data;
}

export async function listMyOrdersRequest() {
  const { data } = await apiClient.get<ApiResponse<Order[]>>("/users/me/orders");
  return data;
}

export async function getMyOrderRequest(orderId: string) {
  const { data } = await apiClient.get<ApiResponse<Order>>(`/users/me/orders/${orderId}`);
  return data;
}
