import type { LanguageCode, UserRole } from "@/types/domain";

export const STORAGE_KEYS = {
  accessToken: "cinema_showcase_access_token",
  userRole: "cinema_showcase_user_role",
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
  sortBy: "start_time",
  sortOrder: "asc",
  limit: "24",
  offset: "0",
};
