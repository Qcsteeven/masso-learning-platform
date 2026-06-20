"use client";
// Auth context stub — real implementation in Phase 3.4.
import { createContext, useContext, useState, type ReactNode } from "react";
import type { MeResponse } from "./types";

interface AuthState {
  user: MeResponse | null;
  accessToken: string | null;
  setAuth: (user: MeResponse, token: string) => void;
  clearAuth: () => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  accessToken: null,
  setAuth: () => {},
  clearAuth: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        setAuth: (u, t) => { setUser(u); setAccessToken(t); },
        clearAuth: () => { setUser(null); setAccessToken(null); },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
