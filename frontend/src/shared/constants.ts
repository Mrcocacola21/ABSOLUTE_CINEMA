import type { LanguageCode, UserRole } from "@/types/domain";

export const STORAGE_KEYS = {
  accessToken: "cinema_showcase_access_token",
  userRole: "cinema_showcase_user_role",
  language: "cinema_showcase_language",
} as const;

export const ROLES: Record<string, UserRole> = {
  USER: "user",
  ADMIN: "admin",
};

export const LANGUAGES: Record<string, LanguageCode> = {
  uk: "uk",
  en: "en",
};

export const DEFAULT_SCHEDULE_PARAMS = {
  day: "",
  genre: "",
  listDay: "",
  dateSort: "nearest",
  seatSort: "",
  query: "",
  sessionId: "",
  limit: "100",
  offset: "0",
};
