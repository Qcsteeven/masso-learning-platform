"use client";
// WebSocket hook stubs — real implementations in Phase 5.3–5.4.
import { useEffect, useRef } from "react";
import type { WsMonitoringEvent, WsSessionEvent, WsStatusEvent, WsTerminalMessage } from "./types";

type NullHook<T> = { data: T | null; send: (msg: unknown) => void };

function useWs<T>(_url: string | null): NullHook<T> {
  useRef<WebSocket | null>(null);  // placeholder — real WebSocket wired in Phase 5
  useEffect(() => {
    // Will be implemented in Phase 5
  }, [_url]);
  return { data: null, send: () => {} };
}

export function useSessionTerminal(sessionId: string | null): NullHook<WsTerminalMessage> {
  return useWs(sessionId ? `/ws/sessions/${sessionId}/terminal` : null);
}

export function useSessionEvents(sessionId: string | null): NullHook<WsSessionEvent> {
  return useWs(sessionId ? `/ws/sessions/${sessionId}/events` : null);
}

export function useSessionStatus(sessionId: string | null): NullHook<WsStatusEvent> {
  return useWs(sessionId ? `/ws/sessions/${sessionId}/status` : null);
}

export function useAdminMonitoring(): NullHook<WsMonitoringEvent> {
  return useWs("/ws/admin/monitoring");
}
