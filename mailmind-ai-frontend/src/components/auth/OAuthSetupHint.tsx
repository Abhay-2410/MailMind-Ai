import { useQuery } from "@tanstack/react-query";

import { API_BASE_URL } from "@/lib/api";

interface OAuthConfig {
  redirect_uri: string;
  backend_public_url: string;
  frontend_callback_url: string;
  google_configured: boolean;
}

export function OAuthSetupHint() {
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

  if (!data || data.google_configured) {
    return null;
  }

  return (
    <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-center text-xs text-amber-900">
      Google OAuth is not configured on the backend. Add{" "}
      <code className="font-mono">GOOGLE_CLIENT_ID</code> and{" "}
      <code className="font-mono">GOOGLE_CLIENT_SECRET</code> to{" "}
      <code className="font-mono">mailmind-ai-backend/.env</code>.
    </p>
  );
}
