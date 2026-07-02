import { Link } from "react-router-dom";
import { FileText, Sparkles } from "lucide-react";

import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatEmailDate, getSenderInitials } from "@/lib/format";
import { ROUTES } from "@/lib/constants";
import type { EmailListResponse } from "@/types/email";

interface SummariesListProps {
  data: EmailListResponse | undefined;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  onRetry: () => void;
  page: number;
  onPageChange: (page: number) => void;
}

export function SummariesList({
  data,
  isLoading,
  isFetching,
  isError,
  onRetry,
  page,
  onPageChange,
}: SummariesListProps) {
  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-44 rounded-2xl" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <EmptyState
        icon={Sparkles}
        title="Unable to load summaries"
        description="Something went wrong while fetching AI summaries."
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
        icon={FileText}
        title="No AI summaries yet"
        description="Open any email from your Inbox and generate a summary. Summarized emails will appear here as cards."
        action={
          <Button asChild>
            <Link to={ROUTES.INBOX}>Go to Inbox</Link>
          </Button>
        }
      />
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className={`space-y-4 transition-opacity ${isFetching ? "opacity-70" : ""}`}>
      <div className="grid gap-4 sm:grid-cols-2">
        {data.items.map((email) => {
          const displayName = email.sender_name?.trim() || email.sender;
          return (
            <Link
              key={email.id}
              to={`${ROUTES.EMAIL}/${email.id}`}
              className="group surface-card block p-5 transition-all hover:border-brand-green/30 hover:shadow-soft dark:hover:shadow-dark-glow"
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-green-soft text-xs font-bold text-brand-green">
                    {getSenderInitials(email.sender_name, email.sender)}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-brand-text">{displayName}</p>
                    <p className="truncate text-xs text-brand-muted">
                      {formatEmailDate(email.received_at)}
                    </p>
                  </div>
                </div>
                <Sparkles className="h-4 w-4 shrink-0 text-brand-green opacity-80" />
              </div>
              <h3 className="line-clamp-1 text-sm font-semibold text-brand-text group-hover:text-brand-green">
                {email.subject || "(No subject)"}
              </h3>
              <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-brand-muted">
                {email.summary_text || email.preview || "No summary available"}
              </p>
            </Link>
          );
        })}
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page <= 1 || isFetching}
            onClick={() => onPageChange(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-brand-muted">
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
      ) : null}
    </div>
  );
}
