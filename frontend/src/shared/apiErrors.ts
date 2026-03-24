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

export function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ErrorResponse>(error)) {
    const apiError = error.response?.data?.error;
    if (apiError?.code === "request_validation_error") {
      return formatValidationErrors(apiError.details) ?? apiError.message;
    }
    return apiError?.message ?? fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
