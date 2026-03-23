import { apiClient } from "@/api/client";
import type { ApiResponse } from "@/types/api";
import type { User } from "@/types/domain";

export interface UpdateProfilePayload {
  name?: string;
  email?: string;
  password?: string;
  current_password?: string;
}

export async function updateCurrentUserRequest(payload: UpdateProfilePayload) {
  const { data } = await apiClient.patch<ApiResponse<User>>("/users/me", payload);
  return data;
}

export async function deactivateCurrentUserRequest() {
  const { data } = await apiClient.delete<ApiResponse<User>>("/users/me");
  return data;
}
