import axios from "axios";

import i18n from "@/i18n";
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
      return i18n.t("errors.api.sessionExpired");
    case 403:
      return i18n.t("errors.api.forbidden");
    case 404:
      return i18n.t("errors.api.notFound");
    case 503:
      return i18n.t("errors.api.unavailable");
    default:
      return null;
  }
}

export function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ErrorResponse>(error)) {
    if (!error.response) {
      return i18n.t("errors.api.network");
    }

    const apiError = error.response?.data?.error;
    if (apiError?.code === "request_validation_error") {
      return formatValidationErrors(apiError.details) ?? i18n.t("errors.api.validation");
    }
    if (apiError?.code === "authentication_error") {
      return i18n.t("errors.api.sessionExpired");
    }
    if (apiError?.code === "authorization_error") {
      return i18n.t("errors.api.forbidden");
    }
    if (apiError?.code === "database_error" || apiError?.code === "internal_server_error") {
      return i18n.t("errors.api.unavailable");
    }
    return getFriendlyHttpErrorMessage(error.response.status) ?? fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
