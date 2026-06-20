"use client";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import type { MeResponse } from "@/lib/types";

// Role → destination route (first matching role wins)
const ROLE_ROUTES: Record<string, string> = {
  student: "/(student)/dashboard",
  teacher: "/(teacher)/groups",
  methodist: "/(methodist)/graph",
  admin: "/(admin)/users",
};

function resolveDestination(me: MeResponse): string {
  for (const role of me.roles) {
    const dest = ROLE_ROUTES[role];
    if (dest) return dest;
  }
  return "/";
}

// Map API error messages / codes to user-readable Russian text
function toUserMessage(raw: string): string {
  const lower = raw.toLowerCase();
  if (
    raw.includes("AUTH_INVALID_CREDENTIALS") ||
    lower.includes("invalid") ||
    lower.includes("credentials") ||
    lower.includes("incorrect")
  ) {
    return "Неверный e-mail или пароль";
  }
  if (lower.includes("429") || lower.includes("too many") || lower.includes("rate")) {
    return "Слишком много попыток, подождите";
  }
  // Otherwise surface the API message directly (already in Russian from backend)
  return raw;
}

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      // login() returns MeResponse directly so we can route without a re-render
      const me = await login(email, password);
      router.push(resolveDestination(me));
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : "Произошла ошибка при входе";
      setErrorMessage(toUserMessage(raw));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.heading}>Вход в систему</h1>

        {errorMessage !== null && (
          <div role="alert" style={styles.errorBanner}>
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div style={styles.field}>
            <label htmlFor="email" style={styles.label}>
              E-mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
              disabled={isSubmitting}
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="password" style={styles.label}>
              Пароль
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              disabled={isSubmitting}
            />
          </div>

          <div style={styles.actions}>
            <button
              type="submit"
              disabled={isSubmitting}
              style={{
                ...styles.submitButton,
                ...(isSubmitting ? styles.submitButtonDisabled : {}),
              }}
            >
              {isSubmitting ? "Вход..." : "Войти"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
// Form layout: label ~33%, input ~67% per ТП conventions.
// Color semantics: blue primary action, red error.

const styles = {
  page: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "100vh",
    backgroundColor: "#f5f5f5",
    padding: "1rem",
  } satisfies React.CSSProperties,

  card: {
    backgroundColor: "#ffffff",
    borderRadius: "8px",
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
    padding: "2rem",
    width: "100%",
    maxWidth: "480px",
  } satisfies React.CSSProperties,

  heading: {
    margin: "0 0 1.5rem",
    fontSize: "1.5rem",
    fontWeight: 600,
    color: "#111827",
  } satisfies React.CSSProperties,

  errorBanner: {
    backgroundColor: "#fef2f2",
    border: "1px solid #fca5a5",
    borderRadius: "4px",
    color: "#b91c1c",
    fontSize: "0.875rem",
    marginBottom: "1rem",
    padding: "0.75rem 1rem",
  } satisfies React.CSSProperties,

  field: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
    marginBottom: "1rem",
  } satisfies React.CSSProperties,

  label: {
    flex: "0 0 33%",
    fontSize: "0.875rem",
    color: "#374151",
    textAlign: "right" as const,
  } satisfies React.CSSProperties,

  input: {
    flex: "1",
    border: "1px solid #d1d5db",
    borderRadius: "4px",
    fontSize: "0.875rem",
    padding: "0.5rem 0.75rem",
    outline: "none",
    width: "100%",
  } satisfies React.CSSProperties,

  actions: {
    display: "flex",
    justifyContent: "flex-end",
    marginTop: "1.5rem",
  } satisfies React.CSSProperties,

  submitButton: {
    backgroundColor: "#2563eb",
    border: "none",
    borderRadius: "4px",
    color: "#ffffff",
    cursor: "pointer",
    fontSize: "0.875rem",
    fontWeight: 500,
    padding: "0.625rem 1.5rem",
  } satisfies React.CSSProperties,

  submitButtonDisabled: {
    backgroundColor: "#93c5fd",
    cursor: "not-allowed",
  } satisfies React.CSSProperties,
} as const;
