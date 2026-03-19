import { STORAGE_KEYS } from "@/shared/constants";
import type { UserRole } from "@/types/domain";

export function getStoredAccessToken(): string | null {
  return window.localStorage.getItem(STORAGE_KEYS.accessToken);
}

export function storeAccessToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEYS.accessToken, token);
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(STORAGE_KEYS.accessToken);
}

export function getStoredRole(): UserRole | null {
  return window.localStorage.getItem(STORAGE_KEYS.userRole) as UserRole | null;
}

export function storeRole(role: UserRole): void {
  window.localStorage.setItem(STORAGE_KEYS.userRole, role);
}

export function clearRole(): void {
  window.localStorage.removeItem(STORAGE_KEYS.userRole);
}
