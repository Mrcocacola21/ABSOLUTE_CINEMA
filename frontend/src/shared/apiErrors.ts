import axios from "axios";

import type { ErrorResponse } from "@/types/api";

function formatValidationErrors(details: ErrorResponse["error"]["details"]): string | null {
  if (!Array.isArray(details) || details.length === 0) {
    return null;
  }

  const messages = details
    .map((detail) => {
      const message = typeof detail.msg === "string" ? detail.msg : null;
      const location = Array.isArray(detail.loc)
        ? detail.loc
            .filter((part) => part !== "body")
            .map((part) => String(part))
            .join(".")
        : "";

      if (!message) {
        return null;
      }

      return location ? `${location}: ${message}` : message;
    })
    .filter((message): message is string => Boolean(message));

  return messages.length > 0 ? messages.join("; ") : null;
}

function getFriendlyHttpErrorMessage(statusCode: number): string | null {
  switch (statusCode) {
    case 401:
      return "Your session is no longer valid. Sign in again to continue.";
    case 403:
      return "You do not have permission to perform this action.";
    case 404:
      return "The requested data could not be found.";
    case 503:
      return "The service is temporarily unavailable. Please try again in a moment.";
    default:
      return null;
  }
}

export function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ErrorResponse>(error)) {
    if (!error.response) {
      return "The server is unavailable right now. Check your connection and try again.";
    }

    const apiError = error.response?.data?.error;
    if (apiError?.code === "request_validation_error") {
      return formatValidationErrors(apiError.details) ?? apiError.message;
    }
    if (apiError?.code === "authentication_error") {
      return "Your session is no longer valid. Sign in again to continue.";
    }
    if (apiError?.code === "authorization_error") {
      return "You do not have permission to perform this action.";
    }
    if (apiError?.code === "database_error" || apiError?.code === "internal_server_error") {
      return "The service is temporarily unavailable. Please try again in a moment.";
    }
    return apiError?.message ?? getFriendlyHttpErrorMessage(error.response.status) ?? fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
