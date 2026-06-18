import { Loader2, Save, User } from "lucide-react";
import { useEffect, useState } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useUpdateSettings } from "@/hooks/useSettings";
import { getSenderInitials } from "@/lib/format";
import { THEME_OPTIONS, TIMEZONE_OPTIONS, type SettingsResponse } from "@/types/settings";

interface ProfileSettingsProps {
  settings: SettingsResponse;
}

export function ProfileSettings({ settings }: ProfileSettingsProps) {
  const updateMutation = useUpdateSettings();
  const [fullName, setFullName] = useState(settings.full_name ?? "");
  const [displayName, setDisplayName] = useState(settings.display_name ?? "");
  const [timezone, setTimezone] = useState(settings.timezone);
  const [theme, setTheme] = useState(settings.theme);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setFullName(settings.full_name ?? "");
    setDisplayName(settings.display_name ?? "");
    setTimezone(settings.timezone);
    setTheme(settings.theme);
  }, [settings]);

  async function handleSave() {
    await updateMutation.mutateAsync({
      full_name: fullName.trim() || null,
      display_name: displayName.trim() || null,
      timezone,
      theme,
    });
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  }

  return (
    <Card className="surface-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <User className="h-5 w-5 text-brand-green" />
          Profile
        </CardTitle>
        <CardDescription>Your account details and display preferences</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-4">
          <Avatar className="h-14 w-14">
            {settings.avatar_url ? <AvatarImage src={settings.avatar_url} alt={fullName} /> : null}
            <AvatarFallback className="bg-brand-green-soft text-brand-green">
              {getSenderInitials(fullName || displayName, settings.email)}
            </AvatarFallback>
          </Avatar>
          <div>
            <p className="font-medium text-brand-text">{settings.email}</p>
            <p className="text-sm text-brand-muted">Signed in with Google</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium text-brand-text">Full name</span>
            <Input value={fullName} onChange={(event) => setFullName(event.target.value)} />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium text-brand-text">Display name</span>
            <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium text-brand-text">Timezone</span>
            <select
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
              className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {TIMEZONE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium text-brand-text">Theme</span>
            <select
              value={theme}
              onChange={(event) => setTheme(event.target.value as typeof theme)}
              className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {THEME_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex items-center gap-3">
          <Button onClick={() => void handleSave()} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save profile
              </>
            )}
          </Button>
          {saved ? <span className="text-sm text-brand-green">Saved</span> : null}
          {updateMutation.isError ? (
            <span className="text-sm text-red-600">{updateMutation.error.message}</span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
