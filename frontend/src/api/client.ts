import axios from "axios";

import { clearAccessToken, clearRole, getStoredAccessToken } from "@/shared/storage";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401 && getStoredAccessToken()) {
      clearAccessToken();
      clearRole();
    }
    return Promise.reject(error);
  },
);

export { apiClient };
