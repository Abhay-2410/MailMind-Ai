import { useQuery } from "@tanstack/react-query";

import { API_BASE_URL } from "@/lib/api";

interface OAuthConfig {
  google_configured: boolean;
  google_console_url: string;
  required_redirect_uris: string[];
  authorized_origins: string[];
}

interface OAuthSetupHintProps {
  /** Show full Google Console setup steps (e.g. after redirect_uri_mismatch). */
  showMismatchHelp?: boolean;
}

export function OAuthSetupHint({ showMismatchHelp = false }: OAuthSetupHintProps) {
  const { data } = useQuery({
    queryKey: ["oauth-config"],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/auth/google/oauth-config`);
      if (!response.ok) return null;
      return response.json() as Promise<OAuthConfig>;
    },
    staleTime: 60_000,
    retry: false,
  });

  if (!data) {
    return null;
  }

  if (!data.google_configured) {
    return (
      <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-center text-xs text-amber-900">
        Google OAuth is not configured on the backend. Add{" "}
        <code className="font-mono">GOOGLE_CLIENT_ID</code> and{" "}
        <code className="font-mono">GOOGLE_CLIENT_SECRET</code> to{" "}
        <code className="font-mono">mailmind-ai-backend/.env</code>.
      </p>
    );
  }

  if (!showMismatchHelp) {
    return null;
  }

  return (
    <details className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-950">
      <summary className="cursor-pointer font-medium">
        Google sign-in blocked? Fix redirect URI in Cloud Console
      </summary>
      <div className="mt-3 space-y-2">
        <p>
          Open{" "}
          <a href={data.google_console_url} target="_blank" rel="noreferrer" className="underline">
            Google Cloud Console
          </a>{" "}
          and add these under your OAuth client:
        </p>
        <p className="font-medium">Authorized redirect URIs</p>
        <ul className="list-inside list-disc font-mono text-[11px]">
          {data.required_redirect_uris.map((uri) => (
            <li key={uri}>{uri}</li>
          ))}
        </ul>
        <p className="font-medium">Authorized JavaScript origins</p>
        <ul className="list-inside list-disc font-mono text-[11px]">
          {data.authorized_origins.map((origin) => (
            <li key={origin}>{origin}</li>
          ))}
        </ul>
      </div>
    </details>
  );
}
