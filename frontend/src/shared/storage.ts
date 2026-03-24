import { STORAGE_KEYS } from "@/shared/constants";
import type { UserRole } from "@/types/domain";

export const AUTH_STORAGE_EVENT = "cinema-showcase-auth-storage-changed";

function notifyAuthStorageChanged(): void {
  window.dispatchEvent(new Event(AUTH_STORAGE_EVENT));
}

export function getStoredAccessToken(): string | null {
  return window.localStorage.getItem(STORAGE_KEYS.accessToken);
}

export function storeAccessToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEYS.accessToken, token);
  notifyAuthStorageChanged();
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(STORAGE_KEYS.accessToken);
  notifyAuthStorageChanged();
}

export function getStoredRole(): UserRole | null {
  return window.localStorage.getItem(STORAGE_KEYS.userRole) as UserRole | null;
}

export function storeRole(role: UserRole): void {
  window.localStorage.setItem(STORAGE_KEYS.userRole, role);
  notifyAuthStorageChanged();
}

export function clearRole(): void {
  window.localStorage.removeItem(STORAGE_KEYS.userRole);
  notifyAuthStorageChanged();
}
