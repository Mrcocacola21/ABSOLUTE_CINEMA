import { apiClient } from "@/api/client";
import type { GenreCode } from "@/shared/genres";
import type { ApiResponse } from "@/types/api";
import type {
  AttendanceReport,
  LocalizedText,
  Movie,
  MovieStatus,
  Session,
  SessionDetails,
  TicketListItem,
  User,
} from "@/types/domain";

export interface MovieCreatePayload {
  title: LocalizedText;
  description: LocalizedText;
  duration_minutes: number;
  poster_url?: string;
  age_rating?: string;
  genres: GenreCode[];
  status: MovieStatus;
}

export interface MovieUpdatePayload {
  title?: Partial<LocalizedText>;
  description?: Partial<LocalizedText>;
  duration_minutes?: number;
  poster_url?: string | null;
  age_rating?: string | null;
  genres?: GenreCode[];
  status?: MovieStatus;
}

export interface SessionCreatePayload {
  movie_id: string;
  start_time: string;
  end_time: string;
  price: number;
}

export interface SessionUpdatePayload {
  movie_id?: string;
  start_time?: string;
  end_time?: string;
  price?: number;
}

export async function listAdminMoviesRequest() {
  const { data } = await apiClient.get<ApiResponse<Movie[]>>("/admin/movies");
  return data;
}

export async function createMovieRequest(payload: MovieCreatePayload) {
  const { data } = await apiClient.post<ApiResponse<Movie>>("/admin/movies", payload);
  return data;
}

export async function getAdminMovieRequest(movieId: string) {
  const { data } = await apiClient.get<ApiResponse<Movie>>(`/admin/movies/${movieId}`);
  return data;
}

export async function updateMovieRequest(movieId: string, payload: MovieUpdatePayload) {
  const { data } = await apiClient.patch<ApiResponse<Movie>>(`/admin/movies/${movieId}`, payload);
  return data;
}

export async function deactivateMovieRequest(movieId: string) {
  const { data } = await apiClient.patch<ApiResponse<Movie>>(`/admin/movies/${movieId}/deactivate`);
  return data;
}

export async function deleteMovieRequest(movieId: string) {
  const { data } = await apiClient.delete<ApiResponse<{ id: string; deleted: boolean }>>(`/admin/movies/${movieId}`);
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

export async function getAdminSessionRequest(sessionId: string) {
  const { data } = await apiClient.get<ApiResponse<SessionDetails>>(`/admin/sessions/${sessionId}`);
  return data;
}

export async function updateSessionRequest(sessionId: string, payload: SessionUpdatePayload) {
  const { data } = await apiClient.patch<ApiResponse<SessionDetails>>(`/admin/sessions/${sessionId}`, payload);
  return data;
}

export async function cancelSessionRequest(sessionId: string) {
  const { data } = await apiClient.patch<ApiResponse<Session>>(`/admin/sessions/${sessionId}/cancel`);
  return data;
}

export async function deleteSessionRequest(sessionId: string) {
  const { data } = await apiClient.delete<ApiResponse<{ id: string; deleted: boolean }>>(`/admin/sessions/${sessionId}`);
  return data;
}

export async function listAdminTicketsRequest() {
  const { data } = await apiClient.get<ApiResponse<TicketListItem[]>>("/admin/tickets");
  return data;
}

export async function listAdminUsersRequest() {
  const { data } = await apiClient.get<ApiResponse<User[]>>("/admin/users");
  return data;
}

export async function getAttendanceRequest() {
  const { data } = await apiClient.get<ApiResponse<AttendanceReport>>("/admin/attendance");
  return data;
}
