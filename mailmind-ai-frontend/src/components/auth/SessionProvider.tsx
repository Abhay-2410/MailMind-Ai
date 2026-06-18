import { useEffect } from "react";

import { useAuthHydrated } from "@/hooks/useAuthHydrated";
import { registerSessionHandlers } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const hydrated = useAuthHydrated();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const setSession = useAuthStore((s) => s.setSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const refreshSession = useAuthStore((s) => s.refreshSession);

  useEffect(() => {
    registerSessionHandlers(setSession, clearSession);
  }, [setSession, clearSession]);

  useEffect(() => {
    if (!hydrated || !isAuthenticated) return;

    refreshSession().catch(() => {
      clearSession();
    });
  }, [hydrated, isAuthenticated, refreshSession, clearSession]);

  return children;
}
