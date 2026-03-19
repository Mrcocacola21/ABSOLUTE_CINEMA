export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
  current_page: number;
  total_pages: number;
}

export interface ApiResponseMeta {
  request_id?: string | null;
  pagination?: PaginationMeta | null;
}

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  meta?: ApiResponseMeta | null;
}

export interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown> | Array<Record<string, unknown>> | null;
  };
}
