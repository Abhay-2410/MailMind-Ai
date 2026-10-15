import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";

import { EmailList } from "@/components/inbox/EmailList";
import { InboxFilters } from "@/components/inbox/InboxFilters";
import { SummariesList } from "@/components/inbox/SummariesList";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useInbox } from "@/hooks/useEmails";
import { useInboxView } from "@/hooks/useInboxView";
import { ROUTES } from "@/lib/constants";
import { formatNumber } from "@/lib/format";
import { SYNC_BUTTON_LABEL } from "@/lib/navigation";
import { useSyncStatus } from "@/providers/SyncProvider";
import { useInboxStore } from "@/stores/inboxStore";

export function InboxPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { view, meta } = useInboxView();
  const { page, setPage, setViewFilter, setCategory, setSearch } = useInboxStore();
  const { data, isLoading, isFetching, isError, refetch } = useInbox();
  const { isSyncing, syncDetail, syncPhase, syncStatus, syncError, needsReconnect, triggerFullSync } =
    useSyncStatus();

  useEffect(() => {
    if (searchParams.get("view") === "categories") {
      navigate(`${ROUTES.DASHBOARD}?section=insights`, { replace: true });
      return;
    }
    setPage(1);
    setSearch("");
    setViewFilter("all");
    setCategory("all");
  }, [navigate, searchParams, setCategory, setPage, setSearch, setViewFilter]);

  const lastSyncedLabel = syncStatus?.last_synced_at
    ? `Last synced ${new Date(syncStatus.last_synced_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })}`
    : "Pull the latest messages from Gmail";

  const gmailTotal = syncStatus?.gmail_total;
  const storedCount = syncStatus?.stored_count;
  const coverageLabel =
    gmailTotal != null && storedCount != null && gmailTotal > 0
      ? `${formatNumber(Math.min(storedCount, gmailTotal))} of ${formatNumber(gmailTotal)} Gmail messages synced`
      : null;

  const statusLine = syncError
    ? syncError.message
    : isSyncing
      ? syncDetail ?? "Syncing inbox…"
      : [lastSyncedLabel, coverageLabel].filter(Boolean).join(" · ");

  const syncButtonLabel = needsReconnect
    ? SYNC_BUTTON_LABEL.reconnect
    : syncPhase === "categorizing" && isSyncing
      ? SYNC_BUTTON_LABEL.categorizing
      : isSyncing
        ? SYNC_BUTTON_LABEL.running
        : SYNC_BUTTON_LABEL.idle;

  const listProps = {
    data,
    isLoading,
    isFetching,
    isError,
    onRetry: () => void refetch(),
    onSync: triggerFullSync,
    isSyncing,
    page,
    onPageChange: setPage,
  };

  return (
    <div className="space-y-6">
      <div className="surface-panel px-4 py-3 sm:px-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-green">{meta.eyebrow}</p>
        <p className="mt-1 text-sm text-muted-foreground">{meta.description}</p>
      </div>

      <Card className="surface-card">
        <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div>
            <p className="text-sm font-medium text-brand-text">
              {data ? `${formatNumber(data.total)} emails` : "Loading…"}
            </p>
            <p className={`text-sm ${syncError ? "text-destructive" : "text-brand-muted"}`}>
              {statusLine}
            </p>
          </div>
          <Button
            onClick={triggerFullSync}
            disabled={isSyncing}
            className="inline-flex shrink-0 items-center justify-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 shrink-0 ${isSyncing ? "animate-spin" : ""}`} />
            <span>{syncButtonLabel}</span>
          </Button>
        </CardContent>
      </Card>

      {view === "inbox" ? (
        <>
          <InboxFilters />
          <EmailList {...listProps} />
        </>
      ) : null}

      {view === "summaries" ? <SummariesList {...listProps} /> : null}
    </div>
  );
}
