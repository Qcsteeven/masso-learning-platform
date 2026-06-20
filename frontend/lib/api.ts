// Typed API client — wraps all HTTP calls to the backend.
// Handles the { request_id, status, data, error } envelope and throws typed errors.
// 401 interception: a single refresh attempt is wired via `setAuthInterceptor`.
import type { ApiResponse, LoginRequest, MeResponse, TokenResponse } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── 401 interceptor registration ─────────────────────────────────────────────
// AuthProvider calls setAuthInterceptor on mount to wire up transparent refresh.
// Using a module-level ref avoids a circular import between api.ts ↔ auth-context.tsx.
type AuthInterceptor = {
  getToken: () => string | null;
  refresh: () => Promise<string | null>;
  logout: () => Promise<void>;
};

let _interceptor: AuthInterceptor | null = null;

export function setAuthInterceptor(interceptor: AuthInterceptor): void {
  _interceptor = interceptor;
}

export function clearAuthInterceptor(): void {
  _interceptor = null;
}

// ─── Core fetch wrapper ────────────────────────────────────────────────────────
async function request<T>(
  path: string,
  init?: RequestInit,
  token?: string,
): Promise<ApiResponse<T>> {
  const resolvedToken = token ?? _interceptor?.getToken() ?? undefined;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (resolvedToken) headers["Authorization"] = `Bearer ${resolvedToken}`;

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
    // Required so the HttpOnly refresh-token cookie is sent on /auth/refresh
    credentials: "include",
    cache: "no-store",
  });

  const envelope = (await res.json()) as ApiResponse<T>;

  // Transparent 401 handling: try refresh once, then retry original request.
  // Skip on login and refresh paths to avoid infinite loops.
  if (
    res.status === 401 &&
    _interceptor !== null &&
    path !== "/auth/refresh" &&
    path !== "/auth/login"
  ) {
    const newToken = await _interceptor.refresh();
    if (newToken === null) {
      // refresh failed — interceptor already called logout
      return envelope;
    }

    // Retry original request with the new token
    const retryHeaders: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
      Authorization: `Bearer ${newToken}`,
    };
    const retryRes = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: retryHeaders,
      credentials: "include",
      cache: "no-store",
    });
    return retryRes.json() as Promise<ApiResponse<T>>;
  }

  return envelope;
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
