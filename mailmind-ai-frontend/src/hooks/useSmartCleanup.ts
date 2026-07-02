import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  SMART_CLEANUP_CATEGORIES,
  UNDO_WINDOW_MS,
  estimateMinutesSaved,
} from "@/lib/smartCleanupCategories";
import {
  deleteCleanupMessagesInChunks,
  fetchSmartCleanupCounts,
  mapSmartCleanupError,
  pollCleanupAnalyze,
  restoreCleanupMessages,
  startCleanupAnalyze,
} from "@/lib/smartCleanupApi";
import type {
  SmartCleanupCategoryId,
  SmartCleanupRowData,
  SmartCleanupRowState,
} from "@/types/cleanup";

function initialRow(): SmartCleanupRowData {
  return {
    state: "idle",
    count: 0,
    analyzeProgress: 0,
    deleteProgress: 0,
    deletedCount: 0,
    totalToDelete: 0,
    messageIds: [],
    samples: [],
    keptCount: 0,
    error: null,
    summary: null,
    undoDeadline: null,
  };
}

function buildInitialRows(): Record<SmartCleanupCategoryId, SmartCleanupRowData> {
  return SMART_CLEANUP_CATEGORIES.reduce(
    (acc, category) => {
      acc[category.id] = initialRow();
      return acc;
    },
    {} as Record<SmartCleanupCategoryId, SmartCleanupRowData>,
  );
}

export function useSmartCleanup() {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(true);
  const [rows, setRows] = useState<Record<SmartCleanupCategoryId, SmartCleanupRowData>>(
    buildInitialRows,
  );
  const [confirmCategory, setConfirmCategory] = useState<SmartCleanupCategoryId | null>(null);
  const [loadingCounts, setLoadingCounts] = useState(true);
  const undoTimersRef = useRef<Map<SmartCleanupCategoryId, number>>(new Map());
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      undoTimersRef.current.forEach((timer) => window.clearTimeout(timer));
      undoTimersRef.current.clear();
    };
  }, []);

  const updateRow = useCallback(
    (categoryId: SmartCleanupCategoryId, patch: Partial<SmartCleanupRowData>) => {
      setRows((prev) => ({
        ...prev,
        [categoryId]: { ...prev[categoryId], ...patch },
      }));
    },
    [],
  );

  const [panelError, setPanelError] = useState<string | null>(null);

  const loadCounts = useCallback(async () => {
    setLoadingCounts(true);
    setPanelError(null);
    try {
      const data = await fetchSmartCleanupCounts();
      if (!isMountedRef.current) return;
      for (const item of data.categories) {
        updateRow(item.category, { count: item.count, error: null });
      }
    } catch (error) {
      if (!isMountedRef.current) return;
      const message = mapSmartCleanupError(error);
      setPanelError(message);
      for (const category of SMART_CLEANUP_CATEGORIES) {
        updateRow(category.id, { error: null });
      }
    } finally {
      if (isMountedRef.current) setLoadingCounts(false);
    }
  }, [updateRow]);

  useEffect(() => {
    void loadCounts();
  }, [loadCounts]);

  const runAnalyze = useCallback(
    async (categoryId: SmartCleanupCategoryId) => {
      updateRow(categoryId, {
        state: "analyzing",
        analyzeProgress: 0,
        error: null,
        summary: null,
      });

      try {
        const started = await startCleanupAnalyze(categoryId, true);
        const result = await pollCleanupAnalyze(started.job_id, (progress) => {
          if (!isMountedRef.current) return;
          updateRow(categoryId, {
            analyzeProgress: progress.progress,
          });
        });

        if (!isMountedRef.current) return null;

        updateRow(categoryId, {
          state: result.delete_count > 0 ? "results_ready" : "done",
          analyzeProgress: 1,
          messageIds: result.message_ids,
          samples: result.samples,
          keptCount: result.kept_count,
          totalToDelete: result.delete_count,
          summary:
            result.delete_count === 0
              ? `No safe deletions found · Kept ${result.kept_count}`
              : null,
        });
        return result;
      } catch (error) {
        if (!isMountedRef.current) return null;
        updateRow(categoryId, {
          state: "idle",
          error: mapSmartCleanupError(error),
        });
        return null;
      }
    },
    [updateRow],
  );

  const analyzeAll = useCallback(async () => {
    for (const category of SMART_CLEANUP_CATEGORIES) {
      await runAnalyze(category.id);
    }
  }, [runAnalyze]);

  const requestClean = useCallback(
    async (categoryId: SmartCleanupCategoryId) => {
      const current = rows[categoryId];
      let result = null;
      if (current.state === "idle" || current.state === "done") {
        result = await runAnalyze(categoryId);
      } else if (current.messageIds.length > 0) {
        setConfirmCategory(categoryId);
        return;
      }
      if (result && result.delete_count > 0) {
        setConfirmCategory(categoryId);
      }
    },
    [rows, runAnalyze],
  );

  const cancelClean = useCallback(() => {
    setConfirmCategory(null);
  }, []);

  const schedulePermanentDelete = useCallback(
    (categoryId: SmartCleanupCategoryId, messageIds: string[]) => {
      const existing = undoTimersRef.current.get(categoryId);
      if (existing) window.clearTimeout(existing);

      const deadline = Date.now() + UNDO_WINDOW_MS;
      updateRow(categoryId, { undoDeadline: deadline });

      const timer = window.setTimeout(() => {
        undoTimersRef.current.delete(categoryId);
        void (async () => {
          try {
            await deleteCleanupMessagesInChunks(messageIds, true, (deleted, total) => {
              if (!isMountedRef.current) return;
              updateRow(categoryId, {
                deleteProgress: deleted / total,
                deletedCount: deleted,
              });
            });
            if (!isMountedRef.current) return;
            updateRow(categoryId, { undoDeadline: null, messageIds: [] });
          } catch (error) {
            if (!isMountedRef.current) return;
            updateRow(categoryId, {
              error: mapSmartCleanupError(error),
              undoDeadline: null,
            });
          }
        })();
      }, UNDO_WINDOW_MS);

      undoTimersRef.current.set(categoryId, timer);
    },
    [updateRow],
  );

  const confirmClean = useCallback(async () => {
    if (!confirmCategory) return;
    const categoryId = confirmCategory;
    const row = rows[categoryId];
    const messageIds = row.messageIds;

    setConfirmCategory(null);
    if (messageIds.length === 0) return;

    updateRow(categoryId, {
      state: "deleting",
      deleteProgress: 0,
      deletedCount: 0,
      totalToDelete: messageIds.length,
      error: null,
    });

    try {
      await deleteCleanupMessagesInChunks(messageIds, false, (deleted, total) => {
        if (!isMountedRef.current) return;
        updateRow(categoryId, {
          deleteProgress: deleted / total,
          deletedCount: deleted,
        });
      });

      if (!isMountedRef.current) return;

      const minutesSaved = estimateMinutesSaved(messageIds.length);
      updateRow(categoryId, {
        state: "done",
        summary: `Cleaned ${messageIds.length} emails · Kept ${row.keptCount} · ~${minutesSaved} mins saved`,
        count: Math.max(0, row.count - messageIds.length),
      });

      schedulePermanentDelete(categoryId, [...messageIds]);

      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
    } catch (error) {
      if (!isMountedRef.current) return;
      updateRow(categoryId, {
        state: "results_ready",
        error: mapSmartCleanupError(error),
      });
    }
  }, [confirmCategory, queryClient, rows, schedulePermanentDelete, updateRow]);

  const undoClean = useCallback(
    async (categoryId: SmartCleanupCategoryId) => {
      const row = rows[categoryId];
      const timer = undoTimersRef.current.get(categoryId);
      if (timer) {
        window.clearTimeout(timer);
        undoTimersRef.current.delete(categoryId);
      }

      if (row.messageIds.length === 0 && row.deletedCount === 0) return;

      const idsToRestore = row.messageIds.length > 0 ? row.messageIds : [];
      try {
        if (idsToRestore.length > 0) {
          await restoreCleanupMessages(idsToRestore);
        }
        updateRow(categoryId, {
          state: "idle",
          undoDeadline: null,
          summary: null,
          deletedCount: 0,
          deleteProgress: 0,
        });
        void loadCounts();
      } catch (error) {
        updateRow(categoryId, { error: mapSmartCleanupError(error) });
      }
    },
    [loadCounts, rows, updateRow],
  );

  const confirmRow = confirmCategory ? rows[confirmCategory] : null;
  const confirmLabel =
    confirmCategory != null
      ? (SMART_CLEANUP_CATEGORIES.find((c) => c.id === confirmCategory)?.label ?? "")
      : "";

  return {
    expanded,
    setExpanded,
    rows,
    loadingCounts,
    analyzeAll,
    runAnalyze,
    requestClean,
    cancelClean,
    confirmClean,
    undoClean,
    loadCounts,
    panelError,
    confirmCategory,
    confirmRow,
    confirmLabel,
  };
}

export type { SmartCleanupRowState };
