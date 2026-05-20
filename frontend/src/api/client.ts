import axios, { type InternalAxiosRequestConfig } from "axios";

import {
  clearAuthStorage,
  getStoredAccessToken,
  getStoredRefreshToken,
  storeAccessToken,
} from "@/shared/storage";
import type { ApiResponse } from "@/types/api";
import type { AccessTokenPayload } from "@/types/domain";

interface AuthRetryRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const AUTH_REFRESH_PATH = "/auth/refresh";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

let refreshPromise: Promise<string> | null = null;

apiClient.interceptors.request.use((config) => {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (!axios.isAxiosError(error) || error.response?.status !== 401 || !error.config) {
      return Promise.reject(error);
    }

    const originalRequest = error.config as AuthRetryRequestConfig;
    if (originalRequest._retry || shouldSkipAuthRefresh(originalRequest.url)) {
      return Promise.reject(error);
    }

    const refreshToken = getStoredRefreshToken();
    if (!refreshToken) {
      clearAuthStorage();
      return Promise.reject(error);
    }

    originalRequest._retry = true;
    try {
      const accessToken = await refreshStoredAccessToken();
      originalRequest.headers.Authorization = `Bearer ${accessToken}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      clearAuthStorage();
      return Promise.reject(refreshError);
    }
  },
);

function shouldSkipAuthRefresh(url?: string): boolean {
  if (!url) {
    return false;
  }
  return url.includes("/auth/login") || url.includes("/auth/token") || url.includes(AUTH_REFRESH_PATH);
}

async function requestAccessTokenRefresh(): Promise<string> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    throw new Error("No refresh token is available.");
  }

  const { data } = await axios.post<ApiResponse<AccessTokenPayload>>(
    `${API_BASE_URL}${AUTH_REFRESH_PATH}`,
    { refresh_token: refreshToken },
    {
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  storeAccessToken(data.data.access_token);
  return data.data.access_token;
}

export function refreshStoredAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = requestAccessTokenRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export { apiClient };
