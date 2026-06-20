// Typed API client — all functions are stubs returning typed promises.
// Real HTTP calls will be implemented in Phase 3.2 (auth) and subsequent phases.
import type { ApiResponse, LoginRequest, MeResponse, TokenResponse } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  init?: RequestInit,
  token?: string,
): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  return res.json() as Promise<ApiResponse<T>>;
}

export const api = {
  auth: {
    login: (body: LoginRequest): Promise<ApiResponse<TokenResponse>> =>
      request("/auth/login", { method: "POST", body: JSON.stringify(body) }),

    me: (token: string): Promise<ApiResponse<MeResponse>> =>
      request("/auth/me", {}, token),

    refresh: (): Promise<ApiResponse<TokenResponse>> =>
      request("/auth/refresh", { method: "POST" }),

    logout: (token: string): Promise<ApiResponse<null>> =>
      request("/auth/logout", { method: "POST" }, token),
  },
};
