import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/types/api";
import type { Ticket, TicketListItem } from "@/types/domain";

export async function listMyTicketsRequest() {
  const { data } = await apiClient.get<ApiResponse<TicketListItem[]>>("/tickets/me");
  return data;
}

export async function cancelTicketRequest(ticketId: string) {
  const { data } = await apiClient.patch<ApiResponse<Ticket>>(`/tickets/${ticketId}/cancel`);
  return data;
}
