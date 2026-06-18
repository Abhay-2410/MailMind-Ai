import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";



import { AuthLayout } from "@/components/auth/AuthLayout";

import { GoogleLoginButton } from "@/components/auth/GoogleLoginButton";

import { OAuthSetupHint } from "@/components/auth/OAuthSetupHint";

import { Button } from "@/components/ui/button";

import { useAuth } from "@/hooks/useAuth";

import { ROUTES } from "@/lib/constants";



export function LoginPage() {

  const navigate = useNavigate();

  const { isAuthenticated, isLoading, loginWithGoogle, loginDev } = useAuth();

  const [googleLoading, setGoogleLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);



  useEffect(() => {

    if (isAuthenticated) {

      navigate(ROUTES.DASHBOARD, { replace: true });

    }

  }, [isAuthenticated, navigate]);



  const handleGoogleLogin = async () => {

    setError(null);

    setGoogleLoading(true);

    try {

      await loginWithGoogle();

    } catch (err) {

      setGoogleLoading(false);

      setError(err instanceof Error ? err.message : "Could not start Google sign-in");

    }

  };



  return (

    <AuthLayout subtitle="Sign in with Google to connect your Gmail inbox">

      <div className="space-y-4">

        <GoogleLoginButton

          onClick={() => void handleGoogleLogin()}

          isLoading={googleLoading}

          disabled={isLoading}

        />



        {error ? (

          <p className="rounded-xl bg-red-50 px-4 py-3 text-center text-sm text-destructive">{error}</p>

        ) : null}



        <OAuthSetupHint />



        <div className="relative py-2">

          <div className="absolute inset-0 flex items-center">

            <span className="w-full border-t border-border" />

          </div>

          <div className="relative flex justify-center text-xs uppercase">

            <span className="bg-white/80 px-2 text-brand-muted">Development</span>

          </div>

        </div>



        <Button

          type="button"

          variant="ghost"

          size="sm"

          className="w-full text-brand-muted"

          onClick={() => void loginDev()}

          disabled={isLoading || googleLoading}

        >

          {isLoading ? "Signing in…" : "Continue without Google (demo)"}

        </Button>

      </div>

    </AuthLayout>

  );

}

