import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/types/api";
import type { Movie, ScheduleItem, SessionDetails, SessionSeats, Ticket } from "@/types/domain";

export interface ScheduleQuery {
  sortBy: string;
  sortOrder: string;
  movieId?: string;
  limit: string;
  offset: string;
}

export async function getScheduleRequest(query: ScheduleQuery) {
  const { data } = await apiClient.get<ApiResponse<ScheduleItem[]>>("/schedule", {
    params: {
      sort_by: query.sortBy,
      sort_order: query.sortOrder,
      movie_id: query.movieId || undefined,
      limit: query.limit,
      offset: query.offset,
    },
  });
  return data;
}

export async function getMoviesRequest(options?: { includeInactive?: boolean }) {
  const { data } = await apiClient.get<ApiResponse<Movie[]>>("/movies", {
    params: {
      include_inactive: options?.includeInactive || undefined,
    },
  });
  return data;
}

export async function getMovieRequest(movieId: string, options?: { includeInactive?: boolean }) {
  const { data } = await apiClient.get<ApiResponse<Movie>>(`/movies/${movieId}`, {
    params: {
      include_inactive: options?.includeInactive || undefined,
    },
  });
  return data;
}

export async function getSessionDetailsRequest(sessionId: string) {
  const { data } = await apiClient.get<ApiResponse<SessionDetails>>(`/schedule/${sessionId}`);
  return data;
}

export async function getSessionSeatsRequest(sessionId: string) {
  const { data } = await apiClient.get<ApiResponse<SessionSeats>>(`/sessions/${sessionId}/seats`);
  return data;
}

export async function purchaseTicketRequest(sessionId: string, row: number, number: number) {
  const { data } = await apiClient.post<ApiResponse<Ticket>>("/tickets/purchase", {
    session_id: sessionId,
    seat_row: row,
    seat_number: number,
  });
  return data;
}
