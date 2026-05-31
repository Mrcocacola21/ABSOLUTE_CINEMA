import type { GenreCode } from "@/shared/genres";

export type LanguageCode = "uk" | "en";
export type UserRole = "user" | "admin";
export type MovieStatus = "planned" | "active" | "deactivated";
export type OrderStatus =
  | "pending_payment"
  | "completed"
  | "partially_cancelled"
  | "payment_failed"
  | "payment_cancelled"
  | "cancelled"
  | "expired";
export type TicketStatus = "reserved" | "purchased" | "cancelled" | "expired";
export type PaymentStatus =
  | "created"
  | "pending"
  | "requires_action"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "expired"
  | "refunded"
  | "partially_refunded";
export type PaymentAttemptStatus = "created" | "pending" | "succeeded" | "failed";
export type RefundStatus = "created" | "pending" | "succeeded" | "failed" | "cancelled";
export type PaymentWebhookProcessingStatus = "received" | "processing" | "processed" | "failed" | "skipped";
export type PaymentSimulationResult = "succeeded" | "failed" | "cancelled" | "pending";
export type CustomerRefundScope = "order" | "tickets";
export type OrderValidationState =
  | "valid"
  | "cancelled"
  | "expired"
  | "payment_failed"
  | "payment_cancelled"
  | "already_used"
  | "invalid_token"
  | "order_not_found"
  | "order_unavailable";

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

export interface AccessTokenPayload {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface TokenPayload extends AccessTokenPayload {
  refresh_token: string;
  refresh_expires_in: number;
}

export interface Movie {
  id: string;
  title: LocalizedText;
  description: LocalizedText;
  duration_minutes: number;
  poster_url?: string | null;
  poster_file_url?: string | null;
  poster_display_url?: string | null;
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
  poster_file_url?: string | null;
  poster_display_url?: string | null;
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
  status: "available" | "reserved" | "purchased";
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
  status: TicketStatus;
  reserved_at?: string | null;
  expires_at?: string | null;
  purchased_at?: string | null;
  updated_at?: string | null;
  cancelled_at?: string | null;
  checked_in_at?: string | null;
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
  order_status?: OrderStatus | null;
  order_created_at?: string | null;
  order_total_price?: number | null;
  order_tickets_count?: number | null;
  order_validation_token?: string | null;
}

export interface OrderTicket {
  id: string;
  order_id?: string | null;
  seat_row: number;
  seat_number: number;
  price: number;
  status: TicketStatus;
  reserved_at?: string | null;
  expires_at?: string | null;
  purchased_at?: string | null;
  updated_at?: string | null;
  cancelled_at?: string | null;
  checked_in_at?: string | null;
  is_cancellable: boolean;
  valid_for_entry: boolean;
  is_refundable: boolean;
  refund_status?: RefundStatus | null;
  refund_id?: string | null;
  refund_amount_minor: number;
}

export interface Order {
  id: string;
  user_id: string;
  session_id: string;
  status: OrderStatus;
  total_price: number;
  tickets_count: number;
  expires_at?: string | null;
  created_at: string;
  updated_at?: string | null;
  movie_id: string;
  movie_title: LocalizedText;
  poster_url?: string | null;
  poster_file_url?: string | null;
  poster_display_url?: string | null;
  age_rating?: string | null;
  session_start_time: string;
  session_end_time: string;
  session_price: number;
  session_status: string;
  active_tickets_count: number;
  reserved_tickets_count: number;
  cancelled_tickets_count: number;
  expired_tickets_count: number;
  checked_in_tickets_count: number;
  unchecked_active_tickets_count: number;
  payment_id?: string | null;
  payment_status?: PaymentStatus | null;
  refunds_count: number;
  refunded_amount_minor: number;
  remaining_refundable_amount_minor: number;
  latest_refund_status?: RefundStatus | null;
  full_refund_available: boolean;
  tickets: OrderTicket[];
}

export interface OrderDetails extends Order {
  valid_for_entry: boolean;
  entry_status_code: string;
  entry_status_message: string;
  validation_token: string;
  validation_url: string;
}

export interface PaymentInitiation {
  payment_id: string;
  order_id: string;
  provider: string;
  status: PaymentStatus;
  amount_minor: number;
  currency: string;
  attempt_id?: string | null;
  attempt_status?: PaymentAttemptStatus | null;
  provider_payment_id?: string | null;
  provider_attempt_id?: string | null;
  redirect_url?: string | null;
  client_payload?: Record<string, unknown> | null;
  expires_at?: string | null;
  reused: boolean;
}

export interface PaymentAttempt {
  id: string;
  payment_id: string;
  order_id: string;
  provider: string;
  provider_attempt_id?: string | null;
  request_payload_snapshot?: Record<string, unknown> | null;
  response_payload_snapshot?: Record<string, unknown> | null;
  status: PaymentAttemptStatus;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface PaymentDetails {
  id: string;
  order_id: string;
  user_id: string;
  amount_minor: number;
  currency: string;
  provider: string;
  provider_payment_id?: string | null;
  idempotency_key: string;
  metadata?: Record<string, unknown> | null;
  status: PaymentStatus;
  failure_code?: string | null;
  failure_message?: string | null;
  created_at: string;
  updated_at?: string | null;
  attempts: PaymentAttempt[];
}

export interface Refund {
  id: string;
  payment_id: string;
  order_id: string;
  user_id: string;
  amount_minor: number;
  currency: string;
  status: RefundStatus;
  provider: string;
  provider_refund_id?: string | null;
  reason: string;
  requested_by: string;
  request_payload_snapshot?: Record<string, unknown> | null;
  response_payload_snapshot?: Record<string, unknown> | null;
  failure_code?: string | null;
  failure_message?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface CustomerRefundRequest {
  scope: CustomerRefundScope;
  ticket_ids?: string[];
  reason?: string | null;
}

export interface CustomerRefundResult {
  refund: Refund;
  payment: PaymentDetails;
  refunds: Refund[];
  refunds_count: number;
  refunded_amount_minor: number;
  remaining_refundable_amount_minor: number;
  latest_refund_status?: RefundStatus | null;
}

export interface PaymentWebhookEvent {
  id: string;
  provider: string;
  provider_event_id?: string | null;
  event_type: string;
  signature_verified: boolean;
  payload_hash: string;
  payload_snapshot?: Record<string, unknown> | null;
  processing_status: PaymentWebhookProcessingStatus;
  processed_at?: string | null;
  error_message?: string | null;
  payment_id?: string | null;
  order_id?: string | null;
  refund_id?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface PaymentWebhookProcessing {
  event_id?: string | null;
  provider: string;
  provider_event_id?: string | null;
  event_type: string;
  processing_status: PaymentWebhookProcessingStatus;
  duplicate: boolean;
  payment_id?: string | null;
  refund_id?: string | null;
  order_id?: string | null;
  message: string;
}

export interface PaymentSimulation {
  result: PaymentSimulationResult;
  payment: PaymentDetails;
  webhook: PaymentWebhookProcessing;
  message: string;
}

export interface AdminPaymentCustomer {
  user_id: string;
  name?: string | null;
  email?: string | null;
}

export interface AdminPaymentTicketImpact {
  id: string;
  seat_row: number;
  seat_number: number;
  seat_label: string;
  price: number;
  status: TicketStatus | string;
  purchased_at?: string | null;
  cancelled_at?: string | null;
  checked_in_at?: string | null;
  refund_id?: string | null;
  refund_status?: RefundStatus | null;
  refund_amount_minor: number;
}

export interface AdminPaymentOrderContext {
  order_id: string;
  order_status?: OrderStatus | string | null;
  session_id?: string | null;
  movie_id?: string | null;
  movie_title?: LocalizedText | null;
  session_start_time?: string | null;
  session_end_time?: string | null;
  session_status?: string | null;
  total_price?: number | null;
  tickets_count: number;
  seats: string[];
  tickets: AdminPaymentTicketImpact[];
  expires_at?: string | null;
}

export interface AdminPaymentListItem extends Omit<PaymentDetails, "attempts"> {
  attempts_count: number;
  refunds_count: number;
  refunded_amount_minor: number;
  remaining_refundable_amount_minor: number;
  refundable: boolean;
  latest_refund_status?: RefundStatus | null;
  order_status?: OrderStatus | string | null;
  customer_name?: string | null;
  customer_email?: string | null;
}

export interface AdminPaymentDetails extends PaymentDetails {
  refunds: Refund[];
  webhook_events: PaymentWebhookEvent[];
  order?: AdminPaymentOrderContext | null;
  customer?: AdminPaymentCustomer | null;
  attempts_count: number;
  refunds_count: number;
  refunded_amount_minor: number;
  remaining_refundable_amount_minor: number;
  refundable: boolean;
  latest_refund_status?: RefundStatus | null;
}

export interface PaymentReportPeriod {
  date_from?: string | null;
  date_to?: string | null;
  payment_timestamp_basis: string;
  refund_timestamp_basis: string;
}

export interface PaymentReportSummary {
  currency: string;
  total_payments_count: number;
  succeeded_payments_count: number;
  failed_payments_count: number;
  pending_payments_count: number;
  cancelled_payments_count: number;
  expired_payments_count: number;
  refunded_payments_count: number;
  partially_refunded_payments_count: number;
  gross_revenue_minor: number;
  refunded_amount_minor: number;
  net_revenue_minor: number;
  succeeded_orders_count: number;
  paid_tickets_count: number;
  success_rate: number;
}

export interface PaymentReportSessionAggregate {
  session_id: string;
  movie_id?: string | null;
  movie_title?: LocalizedText | null;
  session_start_time?: string | null;
  session_end_time?: string | null;
  session_status?: string | null;
  currency: string;
  succeeded_payments_count: number;
  succeeded_orders_count: number;
  paid_tickets_count: number;
  gross_revenue_minor: number;
  refunded_amount_minor: number;
  net_revenue_minor: number;
}

export interface PaymentReportMovieAggregate {
  movie_id: string;
  movie_title?: LocalizedText | null;
  currency: string;
  paid_sessions_count: number;
  succeeded_payments_count: number;
  succeeded_orders_count: number;
  paid_tickets_count: number;
  gross_revenue_minor: number;
  refunded_amount_minor: number;
  net_revenue_minor: number;
}

export interface PaymentReport {
  generated_at: string;
  period: PaymentReportPeriod;
  summary: PaymentReportSummary;
  sessions: PaymentReportSessionAggregate[];
  movies: PaymentReportMovieAggregate[];
}

export interface OrderValidationTicket {
  id: string;
  seat_row: number;
  seat_number: number;
  status: TicketStatus;
  reserved_at?: string | null;
  expires_at?: string | null;
  purchased_at?: string | null;
  cancelled_at?: string | null;
  checked_in_at?: string | null;
  valid_for_entry: boolean;
}

export interface OrderValidationResult {
  scanned_at: string;
  token_status: string;
  order_id?: string | null;
  is_valid_for_entry: boolean;
  validity_code: OrderValidationState;
  message: string;
  can_check_in: boolean;
  order_status?: OrderStatus | null;
  movie_title?: LocalizedText | null;
  session_start_time?: string | null;
  session_end_time?: string | null;
  session_status?: string | null;
  active_tickets_count: number;
  reserved_tickets_count: number;
  cancelled_tickets_count: number;
  expired_tickets_count: number;
  checked_in_tickets_count: number;
  unchecked_active_tickets_count: number;
  tickets: OrderValidationTicket[];
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
  purchased_at: string;
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
