import { LogOut, Shield } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { ROUTES } from "@/lib/constants";
import type { SettingsResponse } from "@/types/settings";

interface SecuritySettingsProps {
  settings: SettingsResponse;
}

export function SecuritySettings({ settings }: SecuritySettingsProps) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate(ROUTES.LOGIN, { replace: true });
  }

  return (
    <Card className="surface-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Shield className="h-5 w-5 text-brand-green" />
          Security
        </CardTitle>
        <CardDescription>Session and account security</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-xl border border-border bg-white/70 p-4 text-sm">
          <p className="text-brand-text">
            <span className="font-medium">Account:</span> {settings.email}
          </p>
          <p className="mt-2 text-brand-muted">
            Sessions use secure JWT access tokens with HTTP-only refresh cookies. Gmail OAuth tokens
            are encrypted at rest.
          </p>
        </div>

        <Button variant="destructive" onClick={() => void handleLogout()}>
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </Button>
      </CardContent>
    </Card>
  );
}
