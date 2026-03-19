import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/types/api";
import type { AttendanceReport, Movie, Session, SessionDetails } from "@/types/domain";

export interface MovieCreatePayload {
  title: string;
  description: string;
  duration_minutes: number;
  poster_url?: string;
  age_rating?: string;
  genres: string[];
  is_active: boolean;
}

export interface MovieUpdatePayload {
  title?: string;
  description?: string;
  duration_minutes?: number;
  poster_url?: string | null;
  age_rating?: string | null;
  genres?: string[];
  is_active?: boolean;
}

export interface SessionCreatePayload {
  movie_id: string;
  start_time: string;
  price: number;
}

export async function listAdminMoviesRequest() {
  const { data } = await apiClient.get<ApiResponse<Movie[]>>("/admin/movies");
  return data;
}

export async function createMovieRequest(payload: MovieCreatePayload) {
  const { data } = await apiClient.post<ApiResponse<Movie>>("/admin/movies", payload);
  return data;
}

export async function updateMovieRequest(movieId: string, payload: MovieUpdatePayload) {
  const { data } = await apiClient.patch<ApiResponse<Movie>>(`/admin/movies/${movieId}`, payload);
  return data;
}

export async function listAdminSessionsRequest() {
  const { data } = await apiClient.get<ApiResponse<SessionDetails[]>>("/admin/sessions");
  return data;
}

export async function createSessionRequest(payload: SessionCreatePayload) {
  const { data } = await apiClient.post<ApiResponse<SessionDetails>>("/admin/sessions", payload);
  return data;
}

export async function cancelSessionRequest(sessionId: string) {
  const { data } = await apiClient.patch<ApiResponse<Session>>(`/admin/sessions/${sessionId}/cancel`);
  return data;
}

export async function getAttendanceRequest() {
  const { data } = await apiClient.get<ApiResponse<AttendanceReport>>("/admin/attendance");
  return data;
}
