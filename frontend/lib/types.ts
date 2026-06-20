// Hand-written TypeScript mirrors of backend Pydantic schemas.
// Will be replaced by generated types once the backend API is stable.

export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiResponse<T> {
  request_id: string;
  status: "success" | "error";
  data?: T;
  error?: ErrorDetail;
}

// ─── Auth ─────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface MeResponse {
  user_id: string;
  email: string;
  full_name: string;
  roles: string[];
  status: string;
}

// ─── Session ──────────────────────────────────────────────────────────────

export type SessionStatus =
  | "created"
  | "starting"
  | "active"
  | "paused"
  | "submitted"
  | "checking"
  | "completed"
  | "failed";

export interface SessionResponse {
  session_id: string;
  run_id: string;
  status: SessionStatus;
  started_at: string;
  finished_at?: string;
  trace_id: string;
}

// ─── WebSocket message discriminated unions ───────────────────────────────

export type WsTerminalMessage =
  | { type: "stdout"; data: string }
  | { type: "stderr"; data: string }
  | { type: "close"; code: number };

export type WsSessionEvent =
  | { type: "incident"; severity: string; message: string; timestamp: string }
  | { type: "hint"; number: number; text: string; penalty_percent: number }
  | { type: "warning"; message: string }
  | { type: "security"; event_type: string; severity: string }
  | { type: "check_status"; check: string; passed: boolean };

export type WsStatusEvent = {
  type: "status_change";
  status: SessionStatus;
  timestamp: string;
};

export type WsMonitoringEvent =
  | { type: "queue"; name: string; depth: number }
  | { type: "provider"; code: string; mode: string; status: string }
  | { type: "sandbox"; session_id: string; action: string }
  | { type: "alert"; severity: string; message: string };
