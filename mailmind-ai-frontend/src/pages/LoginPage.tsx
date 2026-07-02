import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { GoogleLoginButton } from "@/components/auth/GoogleLoginButton";
import { OAuthSetupHint } from "@/components/auth/OAuthSetupHint";
import { useAuth } from "@/hooks/useAuth";
import { ROUTES } from "@/lib/constants";

export function LoginPage() {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading, loginWithGoogle } = useAuth();
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      navigate(ROUTES.DASHBOARD, { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const handleGoogleLogin = () => {
    setError(null);
    setGoogleLoading(true);
    try {
      loginWithGoogle();
    } catch (err) {
      setGoogleLoading(false);
      setError(err instanceof Error ? err.message : "Could not start Google sign-in");
    }
  };

  const oauthMismatch = error?.toLowerCase().includes("redirect_uri") ?? false;

  return (
    <AuthLayout subtitle="Sign in with Google to connect your Gmail inbox">
      <div className="space-y-4">
        <GoogleLoginButton
          onClick={handleGoogleLogin}
          isLoading={googleLoading}
          disabled={isLoading}
        />

        {error ? (
          <p className="rounded-xl bg-red-50 px-4 py-3 text-center text-sm text-destructive">{error}</p>
        ) : null}

        <OAuthSetupHint showMismatchHelp={oauthMismatch} />
      </div>
    </AuthLayout>
  );
}
