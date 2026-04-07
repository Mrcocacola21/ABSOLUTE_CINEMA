import type { GenreCode } from "@/shared/genres";

export type LanguageCode = "uk" | "en";
export type UserRole = "user" | "admin";
export type MovieStatus = "planned" | "active" | "deactivated";
export type OrderStatus = "completed" | "partially_cancelled" | "cancelled";

export interface LocalizedText {
  uk: string;
  en: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface TokenPayload {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Movie {
  id: string;
  title: LocalizedText;
  description: LocalizedText;
  duration_minutes: number;
  poster_url?: string | null;
  age_rating?: string | null;
  genres: GenreCode[];
  status: MovieStatus;
  created_at: string;
  updated_at?: string | null;
}

export interface ScheduleItem {
  id: string;
  movie_id: string;
  movie_title: LocalizedText;
  poster_url?: string | null;
  age_rating?: string | null;
  genres: GenreCode[];
  start_time: string;
  end_time: string;
  price: number;
  status: string;
  available_seats: number;
  total_seats: number;
}

export interface Session {
  id: string;
  movie_id: string;
  start_time: string;
  end_time: string;
  price: number;
  status: string;
  total_seats: number;
  available_seats: number;
  created_at: string;
  updated_at?: string | null;
}

export interface SessionDetails extends Session {
  movie: Movie;
}

export interface SeatAvailability {
  row: number;
  number: number;
  is_available: boolean;
}

export interface SessionSeats {
  session_id: string;
  rows_count: number;
  seats_per_row: number;
  total_seats: number;
  available_seats: number;
  seats: SeatAvailability[];
}

export interface Ticket {
  id: string;
  order_id?: string | null;
  session_id: string;
  user_id: string;
  seat_row: number;
  seat_number: number;
  price: number;
  status: string;
  purchased_at: string;
  updated_at?: string | null;
  cancelled_at?: string | null;
}

export interface TicketListItem extends Ticket {
  movie_id: string;
  movie_title: LocalizedText;
  session_start_time: string;
  session_end_time: string;
  session_status: string;
  is_cancellable: boolean;
  user_name?: string | null;
  user_email?: string | null;
}

export interface OrderTicket {
  id: string;
  order_id?: string | null;
  seat_row: number;
  seat_number: number;
  price: number;
  status: string;
  purchased_at: string;
  updated_at?: string | null;
  cancelled_at?: string | null;
  is_cancellable: boolean;
}

export interface Order {
  id: string;
  user_id: string;
  session_id: string;
  status: OrderStatus;
  total_price: number;
  tickets_count: number;
  created_at: string;
  updated_at?: string | null;
  movie_id: string;
  movie_title: LocalizedText;
  poster_url?: string | null;
  age_rating?: string | null;
  session_start_time: string;
  session_end_time: string;
  session_status: string;
  active_tickets_count: number;
  cancelled_tickets_count: number;
  tickets: OrderTicket[];
}

export interface AttendanceSessionSummary {
  session_id: string;
  movie_title: LocalizedText;
  start_time: string;
  status: string;
  tickets_sold: number;
  total_seats: number;
  available_seats: number;
  attendance_rate: number;
}

export interface AttendanceReport {
  generated_at: string;
  total_sessions: number;
  total_tickets_sold: number;
  sessions: AttendanceSessionSummary[];
}

export interface AttendanceTicketDetails extends Ticket {
  user_name?: string | null;
  user_email?: string | null;
  order_status?: OrderStatus | null;
}

export interface AttendanceSessionDetails {
  generated_at: string;
  session: SessionDetails;
  seat_map: SessionSeats;
  tickets_sold: number;
  attendance_rate: number;
  occupied_tickets: AttendanceTicketDetails[];
}
