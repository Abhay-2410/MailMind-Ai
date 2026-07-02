import { ChevronDown, ChevronUp, Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useInboxTriage, triagePhaseLabel } from "@/hooks/useInboxTriage";
import { useSmartCleanup } from "@/hooks/useSmartCleanup";
import { formatNumber } from "@/lib/format";
import { SMART_CLEANUP_CATEGORIES, UNDO_WINDOW_MS } from "@/lib/smartCleanupCategories";
import type { SmartCleanupCategoryId } from "@/types/cleanup";

import "./SmartCleanupPanel.css";

function ConfidenceBadge({ level }: { level: "HIGH" | "MEDIUM" }) {
  return (
    <span
      className={`smart-cleanup-badge smart-cleanup-badge--${level === "HIGH" ? "high" : "medium"}`}
    >
      {level}
    </span>
  );
}

function ProgressBar({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, Math.round(value * 100)));
  return (
    <div className="smart-cleanup-progress" aria-hidden={pct === 0}>
      <div className="smart-cleanup-progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function UndoCountdown({
  deadline,
  onUndo,
}: {
  deadline: number;
  onUndo: () => void;
}) {
  const [remaining, setRemaining] = useState(() => Math.max(0, deadline - Date.now()));

  useEffect(() => {
    const timer = window.setInterval(() => {
      setRemaining(Math.max(0, deadline - Date.now()));
    }, 200);
    return () => window.clearInterval(timer);
  }, [deadline]);

  if (remaining <= 0) return null;

  return (
    <Button type="button" size="sm" variant="outline" onClick={onUndo}>
      Undo ({Math.ceil(remaining / 1000)}s)
    </Button>
  );
}

function ConfirmModal({
  open,
  label,
  count,
  samples,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  label: string;
  count: number;
  samples: string[];
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;

  return (
    <div className="smart-cleanup-modal-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="smart-cleanup-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="smart-cleanup-confirm-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="smart-cleanup-confirm-title">Confirm cleanup</h3>
        <p className="text-sm text-brand-muted">
          Move <strong>{formatNumber(count)}</strong> emails from <strong>{label}</strong> to Trash?
          You have {UNDO_WINDOW_MS / 1000} seconds to undo before permanent deletion.
        </p>
        {samples.length > 0 ? (
          <ul className="smart-cleanup-modal-samples">
            {samples.slice(0, 3).map((subject) => (
              <li key={subject}>{subject}</li>
            ))}
          </ul>
        ) : null}
        <div className="smart-cleanup-modal-actions">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm}>
            Clean {formatNumber(count)}
          </Button>
        </div>
      </div>
    </div>
  );
}

function InboxTriageSection() {
  const {
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
  } = useInboxTriage();

  const analyzing = triage.state === "analyzing";
  const deleting = triage.state === "deleting";
  const summary = triage.summary;

  return (
    <div className="smart-cleanup-triage">
      <div className="smart-cleanup-triage-header">
        <div className="smart-cleanup-triage-title">
          <span aria-hidden>🧠</span>
          <span>Analyze Entire Inbox</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {triage.undoDeadline ? (
            <UndoCountdown deadline={triage.undoDeadline} onUndo={() => void undoTriageClean()} />
          ) : null}
          <Button
            type="button"
            size="sm"
            onClick={() => void runTriageAnalyze()}
            disabled={analyzing || deleting}
          >
            {analyzing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing…
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Analyze Entire Inbox
              </>
            )}
          </Button>
        </div>
      </div>

      {analyzing ? (
        <div className="smart-cleanup-triage-progress">
          <p className="smart-cleanup-triage-status">
            {triagePhaseLabel(triage.phase, triage.processed, triage.total)}
          </p>
          <ProgressBar value={triage.progress} />
        </div>
      ) : null}

      {triage.error ? <p className="smart-cleanup-error">{triage.error}</p> : null}

      {summary && triage.state !== "analyzing" ? (
        <>
          <div className="smart-cleanup-triage-stats" aria-label="Inbox importance breakdown">
            <div className="smart-cleanup-triage-stat">
              <span className="smart-cleanup-triage-stat-label">CRITICAL</span>
              <span className="smart-cleanup-triage-stat-value">{formatNumber(summary.critical)}</span>
            </div>
            <div className="smart-cleanup-triage-stat">
              <span className="smart-cleanup-triage-stat-label">IMPORTANT</span>
              <span className="smart-cleanup-triage-stat-value">{formatNumber(summary.important)}</span>
            </div>
            <div className="smart-cleanup-triage-stat">
              <span className="smart-cleanup-triage-stat-label">LOW VALUE</span>
              <span className="smart-cleanup-triage-stat-value">{formatNumber(summary.low_value)}</span>
            </div>
            <div className="smart-cleanup-triage-stat">
              <span className="smart-cleanup-triage-stat-label">DISPOSABLE</span>
              <span className="smart-cleanup-triage-stat-value">{formatNumber(summary.disposable)}</span>
            </div>
          </div>
          <div className="smart-cleanup-triage-actions">
            <Button
              type="button"
              size="sm"
              variant="destructive"
              disabled={deleting || lowValueDeletable.count === 0}
              onClick={() => requestTriageClean("LOW_VALUE")}
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Cleaning…
                </>
              ) : (
                `Clean Low Value (${formatNumber(lowValueDeletable.count)})`
              )}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="destructive"
              disabled={deleting || disposableDeletable.count === 0}
              onClick={() => requestTriageClean("DISPOSABLE")}
            >
              Clean Disposable ({formatNumber(disposableDeletable.count)})
            </Button>
          </div>
        </>
      ) : null}

      <ConfirmModal
        open={triage.confirmTier != null}
        label={confirmLabel}
        count={confirmCount}
        samples={confirmSamples}
        onCancel={cancelTriageClean}
        onConfirm={() => void confirmTriageClean()}
      />
    </div>
  );
}

export function SmartCleanupPanel() {
  const {
    expanded,
    setExpanded,
    rows,
    loadingCounts,
    analyzeAll,
    requestClean,
    cancelClean,
    confirmClean,
    undoClean,
    confirmCategory,
    confirmRow,
    confirmLabel,
    panelError,
  } = useSmartCleanup();

  const [analyzingAll, setAnalyzingAll] = useState(false);

  async function handleAnalyzeAll() {
    setAnalyzingAll(true);
    try {
      await analyzeAll();
    } finally {
      setAnalyzingAll(false);
    }
  }

  return (
    <section className="smart-cleanup-panel">
      <div className="smart-cleanup-header">
        <div className="smart-cleanup-title">
          <span aria-hidden>🧹</span>
          <span>Smart Cleanup</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => void handleAnalyzeAll()}
            disabled={analyzingAll}
          >
            {analyzingAll ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing…
              </>
            ) : (
              <>
                <Sparkles className="mr-2 h-4 w-4" />
                Analyze Inbox
              </>
            )}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            aria-label={expanded ? "Collapse Smart Cleanup" : "Expand Smart Cleanup"}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div className="smart-cleanup-tabs" aria-label="Gmail categories">
        {["Primary", "Promotions", "Social", "Updates"].map((tab) => (
          <span key={tab} className="smart-cleanup-tab">
            {tab}
          </span>
        ))}
      </div>

      {expanded ? (
        <div className="smart-cleanup-body">
          {panelError ? (
            <p className="smart-cleanup-error mb-3 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2">
              {panelError}
              {panelError.toLowerCase().includes("sign out") ? (
                <span> Use Settings or the header menu to sign out, then sign in with Google again.</span>
              ) : null}
            </p>
          ) : null}

          <InboxTriageSection />

          {SMART_CLEANUP_CATEGORIES.map((category) => {
            const row = rows[category.id as SmartCleanupCategoryId];
            const showAnalyzeProgress = row.state === "analyzing";
            const showDeleteProgress = row.state === "deleting";

            return (
              <div key={category.id} className="smart-cleanup-row">
                <div className="smart-cleanup-row-name">{category.label}</div>
                <div className="smart-cleanup-row-count">
                  {loadingCounts && row.count === 0 ? "…" : formatNumber(row.count)}
                </div>
                <ConfidenceBadge level={category.confidence} />
                <div>
                  {showAnalyzeProgress ? (
                    <ProgressBar value={row.analyzeProgress} />
                  ) : showDeleteProgress ? (
                    <p className="text-xs text-brand-muted">
                      Deleted {formatNumber(row.deletedCount)} of {formatNumber(row.totalToDelete)}…
                    </p>
                  ) : (
                    <ProgressBar value={0} />
                  )}
                  {showDeleteProgress ? (
                    <ProgressBar value={row.deleteProgress} />
                  ) : null}
                </div>
                <div className="flex items-center gap-2 justify-self-end">
                  {row.undoDeadline ? (
                    <UndoCountdown
                      deadline={row.undoDeadline}
                      onUndo={() => void undoClean(category.id)}
                    />
                  ) : null}
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={
                      row.state === "analyzing" ||
                      row.state === "deleting" ||
                      (row.count === 0 && row.state !== "results_ready")
                    }
                    onClick={() => void requestClean(category.id)}
                  >
                    {row.state === "deleting" ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Cleaning…
                      </>
                    ) : (
                      "Clean"
                    )}
                  </Button>
                </div>
                {row.summary ? (
                  <p className="smart-cleanup-summary">{row.summary}</p>
                ) : null}
                {row.error ? <p className="smart-cleanup-error">{row.error}</p> : null}
              </div>
            );
          })}
        </div>
      ) : null}

      <ConfirmModal
        open={confirmCategory != null && confirmRow != null}
        label={confirmLabel}
        count={confirmRow?.messageIds.length ?? 0}
        samples={confirmRow?.samples ?? []}
        onCancel={cancelClean}
        onConfirm={() => void confirmClean()}
      />
    </section>
  );
}
