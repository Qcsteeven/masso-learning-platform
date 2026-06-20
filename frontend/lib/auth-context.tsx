"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, clearAuthInterceptor, setAuthInterceptor } from "./api";
import type { MeResponse } from "./types";

// ─── Public surface ────────────────────────────────────────────────────────────

interface AuthState {
  user: MeResponse | null;
  /** Access token kept in memory only — never written to localStorage/sessionStorage. */
  accessToken: string | null;
  isLoading: boolean;
  /**
   * Authenticates the user and populates context.
   * Returns the resolved MeResponse so callers can act on it synchronously
   * without waiting for a React re-render cycle.
   * Throws on authentication failure; error.message is user-readable Russian text.
   */
  login(email: string, password: string): Promise<MeResponse>;
  logout(): Promise<void>;
  /** Called automatically by the api.ts interceptor on 401. */
  refreshToken(): Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  accessToken: null,
  isLoading: true,
  login: async () => {
    throw new Error("AuthProvider not mounted");
  },
  logout: async () => {},
  refreshToken: async () => {},
});

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Access token lives only in a ref so it is never serialised to storage.
  // Synchronous reads from the interceptor use the ref; rendered consumers
  // get the state mirror so re-renders occur when the token changes.
  const tokenRef = useRef<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // ── helpers ────────────────────────────────────────────────────────────────

  function storeToken(token: string) {
    tokenRef.current = token;
    setAccessToken(token);
  }

  function clearToken() {
    tokenRef.current = null;
    setAccessToken(null);
  }

  // ── refreshToken ───────────────────────────────────────────────────────────

  const refreshToken = useCallback(async (): Promise<void> => {
    const res = await api.auth.refresh();
    if (res.status === "error" || !res.data) {
      clearToken();
      setUser(null);
      return;
    }
    const newToken = res.data.access_token;
    storeToken(newToken);

    const meRes = await api.auth.me(newToken);
    if (meRes.status === "success" && meRes.data) {
      setUser(meRes.data);
    } else {
      clearToken();
      setUser(null);
    }
  }, []);

  // ── login ──────────────────────────────────────────────────────────────────

  const login = useCallback(
    async (email: string, password: string): Promise<MeResponse> => {
      const res = await api.auth.login({ email, password });
      if (res.status === "error" || !res.data) {
        throw new Error(res.error?.message ?? "Ошибка входа");
      }
      const token = res.data.access_token;
      storeToken(token);

      const meRes = await api.auth.me(token);
      if (meRes.status === "error" || !meRes.data) {
        throw new Error(
          meRes.error?.message ?? "Не удалось получить данные пользователя",
        );
      }
      setUser(meRes.data);
      return meRes.data;
    },
    [],
  );

  // ── logout ─────────────────────────────────────────────────────────────────

  const logout = useCallback(async (): Promise<void> => {
    const token = tokenRef.current;
    clearToken();
    setUser(null);
    if (token) {
      // Best-effort: clear the HttpOnly refresh cookie on the server
      await api.auth.logout(token).catch(() => {});
    }
  }, []);

  // ── mount: restore session from HttpOnly refresh cookie ───────────────────

  useEffect(() => {
    async function restoreSession() {
      setIsLoading(true);
      try {
        await refreshToken();
      } finally {
        setIsLoading(false);
      }
    }
    void restoreSession();
    // refreshToken has a stable identity (useCallback with empty deps);
    // run only on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── register interceptor so api.ts can refresh transparently on 401 ───────

  useEffect(() => {
    setAuthInterceptor({
      getToken: () => tokenRef.current,
      refresh: async (): Promise<string | null> => {
        const res = await api.auth.refresh();
        if (res.status === "error" || !res.data) {
          void logout();
          return null;
        }
        const newToken = res.data.access_token;
        storeToken(newToken);

        const meRes = await api.auth.me(newToken);
        if (meRes.status === "success" && meRes.data) {
          setUser(meRes.data);
        }
        return newToken;
      },
      logout,
    });
    return () => {
      clearAuthInterceptor();
    };
  }, [logout]);

  // ── context value ──────────────────────────────────────────────────────────

  return (
    <AuthContext.Provider
      value={{ user, accessToken, isLoading, login, logout, refreshToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
