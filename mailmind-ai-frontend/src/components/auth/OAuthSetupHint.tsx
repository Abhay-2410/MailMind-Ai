import { useQuery } from "@tanstack/react-query";

import { API_BASE_URL } from "@/lib/api";

interface OAuthConfig {
  google_configured: boolean;
  google_console_url: string;
  redirect_uri: string;
  required_redirect_uris: string[];
  authorized_origins: string[];
}

interface OAuthSetupHintProps {
  /** Show full Google Console setup steps (e.g. after redirect_uri_mismatch). */
  showMismatchHelp?: boolean;
}

export function OAuthSetupHint({ showMismatchHelp = false }: OAuthSetupHintProps) {
  const pageOrigin = typeof window !== "undefined" ? window.location.origin : "";
  const isLocalhost = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(pageOrigin);
  const isVercelHost = /\.vercel\.app$/i.test(pageOrigin);
  const needsSetupHelp = showMismatchHelp || !isLocalhost;

  const { data } = useQuery({
    queryKey: ["oauth-config", pageOrigin],
    queryFn: async () => {
      const qs = pageOrigin ? `?origin=${encodeURIComponent(pageOrigin)}` : "";
      const response = await fetch(`${API_BASE_URL}/auth/google/oauth-config${qs}`);
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

  if (!needsSetupHelp) {
    return null;
  }

  const redirectUris = data.required_redirect_uris.includes(data.redirect_uri)
    ? data.required_redirect_uris
    : [data.redirect_uri, ...data.required_redirect_uris];
  const origins = data.authorized_origins.includes(pageOrigin)
    ? data.authorized_origins
    : [...data.authorized_origins, pageOrigin].filter(Boolean);

  return (
    <details
      open
      className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-950"
    >
      <summary className="cursor-pointer font-medium">
        {isVercelHost
          ? "Access blocked? Add these Vercel URLs in Google Cloud Console"
          : "Google sign-in blocked? Fix OAuth in Cloud Console"}
      </summary>
      <div className="mt-3 space-y-2">
        <p>
          Google shows <strong>Access blocked</strong> when the redirect URI is missing or your
          account is not a Test user. Open{" "}
          <a href={data.google_console_url} target="_blank" rel="noreferrer" className="underline">
            OAuth client
          </a>{" "}
          and paste:
        </p>
        <p className="font-medium">Authorized redirect URIs</p>
        <ul className="list-inside list-disc break-all font-mono text-[11px]">
          {redirectUris.map((uri) => (
            <li key={uri}>{uri}</li>
          ))}
        </ul>
        <p className="font-medium">Authorized JavaScript origins</p>
        <ul className="list-inside list-disc break-all font-mono text-[11px]">
          {origins.map((origin) => (
            <li key={origin}>{origin}</li>
          ))}
        </ul>
        <p>
          Then open{" "}
          <a
            href="https://console.cloud.google.com/apis/credentials/consent"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            OAuth consent screen
          </a>{" "}
          → <strong>Test users</strong> → add the Gmail account you use on this device. Save and
          wait 1–2 minutes before retrying.
        </p>
      </div>
    </details>
  );
}
