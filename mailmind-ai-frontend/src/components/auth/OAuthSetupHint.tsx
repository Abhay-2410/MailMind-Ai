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

function apiOriginFromBase(apiBase: string): string | null {
  try {
    const url = new URL(apiBase, typeof window !== "undefined" ? window.location.origin : "http://localhost");
    if (!/^https?:$/i.test(url.protocol)) return null;
    // "/api/v1" → strip path for callback host
    return url.origin;
  } catch {
    return null;
  }
}

function buildStaticConfig(pageOrigin: string): OAuthConfig | null {
  const apiOrigin = apiOriginFromBase(API_BASE_URL);
  const isAbsoluteApi = /^https?:\/\//i.test(API_BASE_URL);
  if (!isAbsoluteApi || !apiOrigin) return null;

  const redirectUri = `${apiOrigin}/api/v1/auth/google/callback`;
  const required = [
    redirectUri,
    "http://localhost:8000/api/v1/auth/google/callback",
    "http://127.0.0.1:8000/api/v1/auth/google/callback",
  ];
  const origins = [
    pageOrigin,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://mailmind-ai-frontend.vercel.app",
    "https://mailmind-ai-frontend-abhay-ms-projects.vercel.app",
  ].filter((value, index, all) => value && all.indexOf(value) === index);

  return {
    google_configured: true,
    google_console_url: "https://console.cloud.google.com/apis/credentials",
    redirect_uri: redirectUri,
    required_redirect_uris: required,
    authorized_origins: origins,
  };
}

export function OAuthSetupHint({ showMismatchHelp = false }: OAuthSetupHintProps) {
  const pageOrigin = typeof window !== "undefined" ? window.location.origin : "";
  const isLocalhost = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(pageOrigin);
  const isVercelHost = /\.vercel\.app$/i.test(pageOrigin);
  const needsSetupHelp = showMismatchHelp || !isLocalhost;

  const { data } = useQuery({
    queryKey: ["oauth-config", pageOrigin, API_BASE_URL],
    queryFn: async () => {
      const qs = pageOrigin ? `?origin=${encodeURIComponent(pageOrigin)}` : "";
      try {
        const response = await fetch(`${API_BASE_URL}/auth/google/oauth-config${qs}`);
        if (response.ok) {
          return (await response.json()) as OAuthConfig;
        }
      } catch {
        // Fall through to static production hint (oauth-config is 404 in production).
      }
      return buildStaticConfig(pageOrigin);
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
        <code className="font-mono">GOOGLE_CLIENT_SECRET</code> on the API host.
      </p>
    );
  }

  if (!needsSetupHelp) {
    return null;
  }

  const redirectUris = [
    data.redirect_uri,
    ...data.required_redirect_uris.filter((uri) => uri !== data.redirect_uri),
  ];
  const origins = [
    ...(pageOrigin ? [pageOrigin] : []),
    ...data.authorized_origins.filter((origin) => origin !== pageOrigin),
  ];

  return (
    <details
      open
      className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-950"
    >
      <summary className="cursor-pointer font-medium">
        {isVercelHost
          ? "Access blocked? Add these URLs in Google Cloud Console"
          : "Google sign-in blocked? Fix OAuth in Cloud Console"}
      </summary>
      <div className="mt-3 space-y-2">
        <p>
          Google shows <strong>Access blocked</strong> when the redirect URI is missing or your
          account is not a Test user. Production uses the <strong>API host</strong> callback (Render),
          not a Vercel <code className="font-mono">/api</code> path. Open{" "}
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
