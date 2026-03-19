export type LanguageCode = "uk" | "en";
export type UserRole = "user" | "admin";

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
  title: string;
  description: string;
  duration_minutes: number;
  poster_url?: string | null;
  age_rating?: string | null;
  genres: string[];
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface ScheduleItem {
  id: string;
  movie_id: string;
  movie_title: string;
  poster_url?: string | null;
  age_rating?: string | null;
  genres: string[];
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
  session_id: string;
  user_id: string;
  seat_row: number;
  seat_number: number;
  price: number;
  status: string;
  purchased_at: string;
}

export interface AttendanceSessionSummary {
  session_id: string;
  movie_title: string;
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
