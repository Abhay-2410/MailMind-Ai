import type { AuthTokens } from "@/types/auth";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export const GMAIL_REAUTH_CODE = "gmail_reauth_required";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function isGmailReauthError(error: unknown): boolean {
  return error instanceof ApiError && error.code === GMAIL_REAUTH_CODE;
}

type SessionUpdater = (tokens: AuthTokens) => void;
type SessionClearer = () => void;

let onSessionUpdate: SessionUpdater | null = null;
let onSessionClear: SessionClearer | null = null;
let refreshInFlight: Promise<void> | null = null;

export function registerSessionHandlers(update: SessionUpdater, clear: SessionClearer) {
  onSessionUpdate = update;
  onSessionClear = clear;
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
      .join(", ");
  }
  return fallback;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    const code =
      body && typeof body === "object" && typeof (body as { code?: unknown }).code === "string"
        ? (body as { code: string }).code
        : undefined;
    throw new ApiError(extractErrorMessage(body, "Request failed"), response.status, code);
  }
  return response.json() as Promise<T>;
}

async function refreshAccessToken(): Promise<void> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        throw new ApiError("Session expired", response.status);
      }

      const tokens = (await response.json()) as AuthTokens;
      localStorage.setItem("mailmind_access_token", tokens.access_token);
      onSessionUpdate?.(tokens);
    })().finally(() => {
      refreshInFlight = null;
    });
  }

  await refreshInFlight;
}

function shouldAttemptRefresh(path: string, retried: boolean): boolean {
  if (retried) return false;
  if (path.startsWith("/auth/refresh") || path.startsWith("/auth/dev/login")) return false;
  if (path.startsWith("/auth/session/exchange")) return false;
  return true;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  retried = false,
): Promise<T> {
  const accessToken = localStorage.getItem("mailmind_access_token");

  const headers = new Headers(options.headers ?? {});
  headers.set("Content-Type", "application/json");
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const requestUrl = `${API_BASE_URL}${path}`;
  const response = await fetch(requestUrl, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && shouldAttemptRefresh(path, retried)) {
    try {
      await refreshAccessToken();
      return apiRequest<T>(path, options, true);
    } catch {
      localStorage.removeItem("mailmind_access_token");
      onSessionClear?.();
      throw new ApiError("Session expired. Please sign in again.", 401);
    }
  }

  return parseResponse<T>(response);
}

export { API_BASE_URL };
