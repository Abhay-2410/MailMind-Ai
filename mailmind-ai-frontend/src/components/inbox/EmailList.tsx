import { Inbox } from "lucide-react";

import { EmailListItem } from "@/components/inbox/EmailListItem";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/format";
import type { EmailListResponse } from "@/types/email";

interface EmailListProps {
  data: EmailListResponse | undefined;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  onRetry: () => void;
  onSync?: () => void;
  isSyncing?: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

export function EmailList({
  data,
  isLoading,
  isFetching,
  isError,
  onRetry,
  onSync,
  isSyncing,
  page,
  onPageChange,
}: EmailListProps) {
  if (isLoading) {
    return (
      <div className="surface-list divide-y divide-border">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="flex gap-4 px-5 py-4">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <EmptyState
        icon={Inbox}
        title="Unable to load inbox"
        description="Something went wrong while fetching your emails."
        action={
          <Button onClick={onRetry} variant="outline">
            Try again
          </Button>
        }
      />
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="No emails found"
        description={
          data?.total === 0
            ? "Sync Gmail to import your inbox, or adjust your filters."
            : "No emails match your current filters."
        }
        action={
          onSync ? (
            <Button onClick={onSync} disabled={isSyncing}>
              {isSyncing ? "Syncing…" : "Sync Gmail"}
            </Button>
          ) : undefined
        }
      />
    );
  }

  const start = (data.page - 1) * data.page_size + 1;
  const end = start + data.items.length - 1;
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="space-y-4">
      <div
        className={`surface-list transition-opacity ${isFetching ? "opacity-70" : ""}`}
      >
        {data.items.map((email) => (
          <EmailListItem key={email.id} email={email} />
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-brand-muted">
          Showing {formatNumber(start)}–{formatNumber(end)} of {formatNumber(data.total)}
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page <= 1 || isFetching}
            onClick={() => onPageChange(page - 1)}
          >
            Previous
          </Button>
          <span className="min-w-24 text-center text-sm text-brand-muted">
            Page {page} of {totalPages}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!data.has_more || isFetching}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
