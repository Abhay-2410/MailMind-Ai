import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { fetchSyncStatus, syncInbox, type SyncInboxOptions } from "@/hooks/useEmails";
import { formatSyncProgress } from "@/lib/navigation";
import { useAuthStore } from "@/stores/authStore";

const SYNC_POLL_MS = 60_000;
const STATUS_POLL_MS = 1_000;

/**
 * Full Gmail sync on login (background), incremental sync every minute.
 * Polls /inbox/sync/status while a full sync is running.
 */
export function useAutoSync() {
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const userEmail = useAuthStore((s) => s.user?.email);
  const hasInitialSynced = useRef(false);

  const statusQuery = useQuery({
    queryKey: ["inbox-sync-status"],
    queryFn: fetchSyncStatus,
    enabled: isAuthenticated && userEmail !== "demo@example.com",
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? STATUS_POLL_MS : false,
  });

  const isBackgroundSyncing = statusQuery.data?.status === "running";

  const { mutate, error, isPending } = useMutation({
    mutationFn: (options: SyncInboxOptions = {}) => syncInbox(options),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["inbox-sync-status"] });
      if (variables?.syncAll) {
        return;
      }
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  useEffect(() => {
    if (statusQuery.data?.status !== "running") {
      if (statusQuery.data?.status === "completed" || statusQuery.data?.status === "failed") {
        void queryClient.invalidateQueries({ queryKey: ["inbox"] });
        void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      }
      return;
    }

    void queryClient.invalidateQueries({ queryKey: ["inbox"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  }, [
    statusQuery.data?.status,
    statusQuery.data?.fetched_count,
    statusQuery.data?.new_count,
    queryClient,
  ]);

  useEffect(() => {
    if (!isAuthenticated || hasInitialSynced.current) return;
    if (userEmail === "demo@example.com") return;

    hasInitialSynced.current = true;
    mutate({ syncAll: true, maxResults: 500 });
  }, [isAuthenticated, userEmail, mutate]);

  useEffect(() => {
    if (!isAuthenticated || userEmail === "demo@example.com") return;

    const intervalId = window.setInterval(() => {
      if (isPending || isBackgroundSyncing) return;
      mutate({ incremental: true, maxResults: 100 });
    }, SYNC_POLL_MS);

    return () => window.clearInterval(intervalId);
  }, [isAuthenticated, userEmail, mutate, isBackgroundSyncing, isPending]);

  const syncDetail =
    isBackgroundSyncing && statusQuery.data
      ? formatSyncProgress(statusQuery.data.fetched_count, statusQuery.data.new_count)
      : null;

  return {
    isSyncing: isBackgroundSyncing,
    syncStatus: statusQuery.data,
    syncDetail,
    syncError: error ?? (statusQuery.data?.error ? new Error(statusQuery.data.error) : null),
    triggerFullSync: () => mutate({ syncAll: true, maxResults: 500 }),
  };
}
