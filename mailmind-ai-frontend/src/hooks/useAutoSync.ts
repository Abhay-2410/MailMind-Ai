import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { syncInbox } from "@/hooks/useEmails";
import { useAuthStore } from "@/stores/authStore";

/**
 * Sync Gmail once per authenticated session (Google users only).
 * Demo accounts have no Gmail connection and are skipped silently.
 */
export function useAutoSync() {
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const userEmail = useAuthStore((s) => s.user?.email);
  const hasSynced = useRef(false);

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => syncInbox({ syncAll: true, maxResults: 200 }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  useEffect(() => {
    if (!isAuthenticated || hasSynced.current) return;
    if (userEmail === "demo@example.com") return;

    hasSynced.current = true;
    mutate();
  }, [isAuthenticated, userEmail, mutate]);

  return {
    isSyncing: isPending,
    syncError: error,
  };
}
