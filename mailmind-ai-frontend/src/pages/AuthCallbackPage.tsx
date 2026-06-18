import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { AuthLayout } from "@/components/auth/AuthLayout";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/useAuth";
import { ROUTES } from "@/lib/constants";

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { exchangeSessionCode } = useAuth();
  const [exchangeError, setExchangeError] = useState<string | null>(null);

  const code = params.get("code");
  const error = params.get("error");

  useEffect(() => {
    if (error) return;
    if (!code) {
      navigate(ROUTES.LOGIN, { replace: true });
      return;
    }
    void exchangeSessionCode(code)
      .then(() => navigate(ROUTES.DASHBOARD, { replace: true }))
      .catch((err: unknown) => {
        setExchangeError(err instanceof Error ? err.message : "Session exchange failed");
      });
  }, [code, error, exchangeSessionCode, navigate]);

  const displayError = error ?? exchangeError;

  if (displayError) {
    return (
      <AuthLayout title="Sign in failed" subtitle="Something went wrong during authentication">
        <p className="mb-6 rounded-xl bg-red-50 px-4 py-3 text-center text-sm text-destructive">
          {displayError}
        </p>
        <Button className="w-full" onClick={() => navigate(ROUTES.LOGIN, { replace: true })}>
          Back to login
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Almost there" subtitle="Setting up your session">
      <div className="flex flex-col items-center py-4">
        <Skeleton className="mb-4 h-12 w-12 rounded-full" />
        <p className="text-body">Signing you in…</p>
      </div>
    </AuthLayout>
  );
}
