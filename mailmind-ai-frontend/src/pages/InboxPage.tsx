import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { EmailList } from "@/components/inbox/EmailList";
import { InboxFilters } from "@/components/inbox/InboxFilters";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useInbox, syncInbox } from "@/hooks/useEmails";
import { formatNumber } from "@/lib/format";
import { useInboxStore } from "@/stores/inboxStore";

export function InboxPage() {
  const queryClient = useQueryClient();
  const { page, setPage } = useInboxStore();
  const { data, isLoading, isFetching, isError, refetch } = useInbox();

  const syncMutation = useMutation({
    mutationFn: () => syncInbox({ syncAll: true, maxResults: 200 }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const lastSynced = syncMutation.data?.last_synced_at
    ? new Date(syncMutation.data.last_synced_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="space-y-6">
      <Card className="surface-card">
        <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div>
            <p className="text-sm font-medium text-brand-text">
              {data ? `${formatNumber(data.total)} emails` : "Loading inbox…"}
            </p>
            <p className="text-sm text-brand-muted">
              {syncMutation.isSuccess
                ? `Synced ${formatNumber(syncMutation.data.new_count)} new · ${lastSynced}`
                : "Pull the latest messages from Gmail"}
            </p>
          </div>
          <Button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="shrink-0"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
            {syncMutation.isPending ? "Syncing…" : "Sync Inbox"}
          </Button>
        </CardContent>
      </Card>

      <InboxFilters />

      <EmailList
        data={data}
        isLoading={isLoading}
        isFetching={isFetching}
        isError={isError}
        onRetry={() => void refetch()}
        onSync={() => syncMutation.mutate()}
        isSyncing={syncMutation.isPending}
        page={page}
        onPageChange={setPage}
      />
    </div>
  );
}
