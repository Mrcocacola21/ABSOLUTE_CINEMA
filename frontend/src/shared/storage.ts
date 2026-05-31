import { STORAGE_KEYS } from "@/shared/constants";
import type { UserRole } from "@/types/domain";

export const AUTH_STORAGE_EVENT = "cinema-showcase-auth-storage-changed";

function notifyAuthStorageChanged(): void {
  window.dispatchEvent(new Event(AUTH_STORAGE_EVENT));
}

export function getStoredAccessToken(): string | null {
  return window.localStorage.getItem(STORAGE_KEYS.accessToken);
}

export function getStoredRefreshToken(): string | null {
  return window.localStorage.getItem(STORAGE_KEYS.refreshToken);
}

export function storeAccessToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEYS.accessToken, token);
  notifyAuthStorageChanged();
}

export function storeRefreshToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEYS.refreshToken, token);
  notifyAuthStorageChanged();
}

export function storeAuthTokens(tokens: { accessToken: string; refreshToken: string }): void {
  window.localStorage.setItem(STORAGE_KEYS.accessToken, tokens.accessToken);
  window.localStorage.setItem(STORAGE_KEYS.refreshToken, tokens.refreshToken);
  notifyAuthStorageChanged();
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(STORAGE_KEYS.accessToken);
  notifyAuthStorageChanged();
}

export function clearRefreshToken(): void {
  window.localStorage.removeItem(STORAGE_KEYS.refreshToken);
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

export function clearAuthStorage(): void {
  window.localStorage.removeItem(STORAGE_KEYS.accessToken);
  window.localStorage.removeItem(STORAGE_KEYS.refreshToken);
  window.localStorage.removeItem(STORAGE_KEYS.userRole);
  clearPrivateNavigationStorage();
  notifyAuthStorageChanged();
}

export function rememberProtectedRedirect(path: string): void {
  window.sessionStorage.setItem(STORAGE_KEYS.postLoginRedirect, path);
  window.sessionStorage.setItem(STORAGE_KEYS.lastProtectedRoute, path);
}

export function getRememberedProtectedRedirect(): string | null {
  return window.sessionStorage.getItem(STORAGE_KEYS.postLoginRedirect);
}

export function clearPrivateNavigationStorage(): void {
  window.sessionStorage.removeItem(STORAGE_KEYS.postLoginRedirect);
  window.sessionStorage.removeItem(STORAGE_KEYS.lastProtectedRoute);
}
