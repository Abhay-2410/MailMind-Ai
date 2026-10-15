import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { driveSync, fetchSyncStatus, syncInbox, type SyncInboxOptions } from "@/hooks/useEmails";
import { isGmailReauthError } from "@/lib/api";
import { startGmailReconnect } from "@/lib/gmailReconnect";
import { formatSyncProgress } from "@/lib/navigation";
import { useAuthStore } from "@/stores/authStore";
import type { SyncStatusResponse } from "@/types/email";

/** Near real-time incremental sync (Gmail History API on the backend). */
const SYNC_POLL_MS = 15_000;
const STATUS_POLL_MS = 1_000;
const RECONCILE_STATUS_POLL_MS = 5_000;
const IDLE_STATUS_POLL_MS = 15_000;
const SMART_SYNC: SyncInboxOptions = { syncAll: true, auto: true };
const RECONNECT_MESSAGE = "Gmail access expired — reconnect to keep your inbox in sync.";
/** A drive step that returns this fast was a no-op (another tab holds the lease). */
const DRIVE_MIN_STEP_MS = 2_000;
const DRIVE_IDLE_WAIT_MS = 3_000;
const DRIVE_MAX_RETRY_MS = 30_000;

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

/**
 * Smart sync on login (full only for a first sync; otherwise a fast history sync, with a
 * quiet daily re-list on the backend), then incremental sync every 15s.
 * Must be mounted once via SyncProvider.
 */
export function useAutoSync() {
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const userEmail = useAuthStore((s) => s.user?.email);
  const hasInitialSynced = useRef(false);
  const [reconnectError, setReconnectError] = useState<Error | null>(null);
  const enabled = isAuthenticated && userEmail !== "demo@example.com";

  const statusQuery = useQuery({
    queryKey: ["inbox-sync-status"],
    queryFn: fetchSyncStatus,
    enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status !== "running") return IDLE_STATUS_POLL_MS;
      return data.mode === "reconcile" ? RECONCILE_STATUS_POLL_MS : STATUS_POLL_MS;
    },
  });

  const status = statusQuery.data;
  const phase = status?.phase ?? "idle";
  const isJobRunning = status?.status === "running";
  // Daily reconciles run quietly; only first/explicit full syncs block the UI.
  const isVisibleJob = isJobRunning && status?.mode !== "reconcile";

  const { mutate, error, isPending, variables } = useMutation({
    mutationFn: (options: SyncInboxOptions = {}) => syncInbox(options),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["inbox-sync-status"] });
      if (data.background) return;
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => {
      if (isGmailReauthError(err)) {
        void queryClient.invalidateQueries({ queryKey: ["inbox-sync-status"] });
      }
    },
  });

  const needsReconnect = Boolean(status?.needs_reconnect) || isGmailReauthError(error);
  const isManualPending = isPending && Boolean(variables?.syncAll);
  const isClientDriven = status?.driver === "client";

  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;
  const isDriving = useRef(false);

  // Serverless backend: keep calling /sync/drive while a full sync is running.
  useEffect(() => {
    if (!enabled || !isClientDriven || !isJobRunning || isDriving.current) return;
    isDriving.current = true;
    void (async () => {
      let retryMs = DRIVE_IDLE_WAIT_MS;
      try {
        while (enabledRef.current) {
          const startedAt = Date.now();
          let next: SyncStatusResponse;
          try {
            next = await driveSync();
          } catch (err) {
            if (isGmailReauthError(err)) {
              void queryClient.invalidateQueries({ queryKey: ["inbox-sync-status"] });
              return;
            }
            await sleep(retryMs);
            retryMs = Math.min(retryMs * 2, DRIVE_MAX_RETRY_MS);
            continue;
          }
          retryMs = DRIVE_IDLE_WAIT_MS;
          queryClient.setQueryData(["inbox-sync-status"], next);
          if (next.status !== "running") return;
          if (Date.now() - startedAt < DRIVE_MIN_STEP_MS) await sleep(DRIVE_IDLE_WAIT_MS);
        }
      } finally {
        isDriving.current = false;
      }
    })();
  }, [enabled, isClientDriven, isJobRunning, queryClient]);

  useEffect(() => {
    if (!status) return;
    if (status.status === "running" && status.mode === "reconcile") return;
    if (status.status === "running" || status.status === "completed" || status.status === "failed") {
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  }, [status?.status, status?.phase, status?.fetched_count, status?.new_count, status?.mode, queryClient]);

  useEffect(() => {
    if (!enabled || hasInitialSynced.current) return;
    hasInitialSynced.current = true;
    mutate(SMART_SYNC);
  }, [enabled, mutate]);

  useEffect(() => {
    if (!enabled || needsReconnect) return;

    const intervalId = window.setInterval(() => {
      if (isPending || isJobRunning) return;
      mutate({ incremental: true, maxResults: 200 });
    }, SYNC_POLL_MS);

    return () => window.clearInterval(intervalId);
  }, [enabled, mutate, isJobRunning, isPending, needsReconnect]);

  const syncDetail = (() => {
    if (!isVisibleJob || !status) return null;
    if (phase === "categorizing") {
      return "Categorizing emails…";
    }
    return formatSyncProgress(
      status.listed_count,
      status.fetched_count,
      status.new_count,
      status.gmail_total,
    );
  })();

  const syncError: Error | null = needsReconnect
    ? new Error(RECONNECT_MESSAGE)
    : reconnectError ??
      error ??
      (status?.status === "failed" && status.mode !== "reconcile" && status.error
        ? new Error(status.error)
        : null);

  const triggerSync = () => {
    if (needsReconnect) {
      setReconnectError(null);
      startGmailReconnect().catch(() =>
        setReconnectError(new Error("Could not start Gmail reconnect. Try signing in again.")),
      );
      return;
    }
    mutate(SMART_SYNC);
  };

  return {
    isSyncing: isVisibleJob || isManualPending,
    syncPhase: phase,
    syncStatus: status,
    syncDetail,
    syncError,
    needsReconnect,
    triggerFullSync: triggerSync,
  };
}
