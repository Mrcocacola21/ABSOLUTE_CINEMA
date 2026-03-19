import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/types/api";
import type { TokenPayload, User } from "@/types/domain";

export interface RegisterPayload {
  email: string;
  name: string;
  password: string;
}

export async function loginRequest(email: string, password: string) {
  const formData = new URLSearchParams();
  formData.set("username", email);
  formData.set("password", password);

  const { data } = await apiClient.post<ApiResponse<TokenPayload>>("/auth/login", formData, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
  return data;
}

export async function registerRequest(payload: RegisterPayload) {
  const { data } = await apiClient.post<ApiResponse<User>>("/auth/register", payload);
  return data;
}

export async function getCurrentUserRequest() {
  const { data } = await apiClient.get<ApiResponse<User>>("/users/me");
  return data;
}
