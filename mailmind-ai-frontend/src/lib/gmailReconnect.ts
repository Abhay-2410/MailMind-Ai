import { apiRequest } from "@/lib/api";

interface GoogleReconnectResponse {
  authorization_url: string;
  state: string;
}

/** Starts a fresh Google consent flow for the connected Gmail account (full-page redirect). */
export async function startGmailReconnect(): Promise<void> {
  const origin = encodeURIComponent(window.location.origin);
  const data = await apiRequest<GoogleReconnectResponse>(`/auth/google/reconnect?origin=${origin}`, {
    method: "POST",
  });
  window.location.assign(data.authorization_url);
}
