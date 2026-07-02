import { useEffect } from "react";

import { useAuthHydrated } from "@/hooks/useAuthHydrated";
import { useSettings } from "@/hooks/useSettings";
import { applyTheme, getStoredTheme } from "@/lib/theme";
import { useAuthStore } from "@/stores/authStore";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const hydrated = useAuthHydrated();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data: settings } = useSettings({ enabled: isAuthenticated });

  useEffect(() => {
    if (!hydrated) return;
    const theme = (isAuthenticated && settings?.theme) || getStoredTheme() || "light";
    applyTheme(theme);
  }, [hydrated, isAuthenticated, settings?.theme]);

  useEffect(() => {
    if (!settings || settings.theme !== "system") return;

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [settings?.theme]);

  return children;
}
