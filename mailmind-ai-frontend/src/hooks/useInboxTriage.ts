import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { UNDO_WINDOW_MS } from "@/lib/smartCleanupCategories";
import {
  deleteCleanupMessagesInChunks,
  deleteTriageTier,
  mapSmartCleanupError,
  pollTriageAnalyze,
  restoreCleanupMessages,
  startTriageAnalyze,
} from "@/lib/smartCleanupApi";
import type { ImportanceTier, InboxTriageData, TriageDeleteTier } from "@/types/cleanup";

function initialTriageState(): InboxTriageData {
  return {
    state: "idle",
    processed: 0,
    total: 0,
    progress: 0,
    phase: null,
    summary: null,
    error: null,
    undoDeadline: null,
    deletedMessageIds: [],
    confirmTier: null,
  };
}

export function triagePhaseLabel(phase: string | null, processed: number, total: number): string {
  if (phase === "collecting_ids") return `Scanning inbox… ${processed.toLocaleString()} found`;
  if (phase === "fetching_metadata") {
    return `Loading metadata… ${processed.toLocaleString()} of ${total.toLocaleString()} emails`;
  }
  if (phase === "classifying") {
    return `Analyzing ${processed.toLocaleString()} of ${total.toLocaleString()} emails…`;
  }
  if (total > 0) {
    return `Analyzing ${processed.toLocaleString()} of ${total.toLocaleString()} emails…`;
  }
  return "Starting inbox analysis…";
}

function countDeletable(
  summary: InboxTriageData["summary"],
  tier: TriageDeleteTier,
): { count: number; samples: string[] } {
  if (!summary) return { count: 0, samples: [] };

  const tiers: ImportanceTier[] =
    tier === "both" ? ["LOW_VALUE", "DISPOSABLE"] : [tier === "LOW_VALUE" ? "LOW_VALUE" : "DISPOSABLE"];

  let count = 0;
  const samples: string[] = [];

  for (const item of Object.values(summary.classifications)) {
    if (!item.safe_to_delete || !tiers.includes(item.tier)) continue;
    count += 1;
    if (item.subject && samples.length < 3) {
      samples.push(item.subject);
    }
  }

  return { count, samples };
}

export function useInboxTriage() {
  const queryClient = useQueryClient();
  const [triage, setTriage] = useState<InboxTriageData>(initialTriageState);
  const undoTimerRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (undoTimerRef.current) window.clearTimeout(undoTimerRef.current);
    };
  }, []);

  const updateTriage = useCallback((patch: Partial<InboxTriageData>) => {
    setTriage((prev) => ({ ...prev, ...patch }));
  }, []);

  const runTriageAnalyze = useCallback(async () => {
    updateTriage({
      state: "analyzing",
      processed: 0,
      total: 0,
      progress: 0,
      phase: "pending",
      error: null,
      summary: null,
      confirmTier: null,
    });

    try {
      const started = await startTriageAnalyze(true);
      const result = await pollTriageAnalyze(started.job_id, (progress) => {
        if (!isMountedRef.current) return;
        updateTriage({
          processed: progress.processed,
          total: progress.total,
          progress: progress.progress,
          phase: progress.phase,
        });
      });

      if (!isMountedRef.current) return null;

      updateTriage({
        state: "complete",
        progress: 1,
        summary: result,
        processed: result.total_scanned,
        total: result.total_scanned,
        phase: "completed",
      });
      return result;
    } catch (error) {
      if (!isMountedRef.current) return null;
      updateTriage({
        state: "idle",
        error: mapSmartCleanupError(error),
      });
      return null;
    }
  }, [updateTriage]);

  const requestTriageClean = useCallback(
    (tier: TriageDeleteTier) => {
      if (!triage.summary) return;
      updateTriage({ confirmTier: tier });
    },
    [triage.summary, updateTriage],
  );

  const cancelTriageClean = useCallback(() => {
    updateTriage({ confirmTier: null });
  }, [updateTriage]);

  const schedulePermanentDelete = useCallback(
    (messageIds: string[]) => {
      if (undoTimerRef.current) window.clearTimeout(undoTimerRef.current);

      const deadline = Date.now() + UNDO_WINDOW_MS;
      updateTriage({ undoDeadline: deadline, deletedMessageIds: messageIds });

      undoTimerRef.current = window.setTimeout(() => {
        undoTimerRef.current = null;
        void (async () => {
          try {
            await deleteCleanupMessagesInChunks(messageIds, true, () => {});
            if (!isMountedRef.current) return;
            updateTriage({ undoDeadline: null, deletedMessageIds: [] });
          } catch (error) {
            if (!isMountedRef.current) return;
            updateTriage({ error: mapSmartCleanupError(error), undoDeadline: null });
          }
        })();
      }, UNDO_WINDOW_MS);
    },
    [updateTriage],
  );

  const confirmTriageClean = useCallback(async () => {
    const tier = triage.confirmTier;
    if (!tier || !triage.summary) return;

    updateTriage({ confirmTier: null, state: "deleting", error: null });

    try {
      const result = await deleteTriageTier(tier);
      if (!isMountedRef.current) return;

      updateTriage({
        state: "complete",
        deletedMessageIds: result.message_ids,
      });

      schedulePermanentDelete(result.message_ids);

      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["smart-cleanup-counts"] });
    } catch (error) {
      if (!isMountedRef.current) return;
      updateTriage({
        state: "complete",
        error: mapSmartCleanupError(error),
      });
    }
  }, [queryClient, schedulePermanentDelete, triage.confirmTier, triage.summary, updateTriage]);

  const undoTriageClean = useCallback(async () => {
    if (undoTimerRef.current) {
      window.clearTimeout(undoTimerRef.current);
      undoTimerRef.current = null;
    }

    const ids = triage.deletedMessageIds;
    if (ids.length === 0) return;

    try {
      await restoreCleanupMessages(ids);
      updateTriage({
        undoDeadline: null,
        deletedMessageIds: [],
        error: null,
      });
    } catch (error) {
      updateTriage({ error: mapSmartCleanupError(error) });
    }
  }, [triage.deletedMessageIds, updateTriage]);

  const confirmCount = triage.confirmTier
    ? countDeletable(triage.summary, triage.confirmTier).count
    : 0;
  const confirmSamples = triage.confirmTier
    ? countDeletable(triage.summary, triage.confirmTier).samples
    : [];
  const confirmLabel =
    triage.confirmTier === "LOW_VALUE"
      ? "Low Value"
      : triage.confirmTier === "DISPOSABLE"
        ? "Disposable"
        : "Low Value & Disposable";

  const lowValueDeletable = countDeletable(triage.summary, "LOW_VALUE");
  const disposableDeletable = countDeletable(triage.summary, "DISPOSABLE");

  return {
    triage,
    runTriageAnalyze,
    requestTriageClean,
    cancelTriageClean,
    confirmTriageClean,
    undoTriageClean,
    confirmCount,
    confirmSamples,
    confirmLabel,
    lowValueDeletable,
    disposableDeletable,
  };
}
