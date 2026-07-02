import { ArrowRight, Clock, MessageSquareReply } from "lucide-react";
import { Link } from "react-router-dom";

import { MetricPill, PremiumCard } from "@/components/design-system";
import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/format";
import type { FollowUpsData, SmartRepliesData } from "@/lib/dashboard/intelligenceMappers";

interface SmartRepliesCardProps {
  data: SmartRepliesData;
}

export function SmartRepliesCard({ data }: SmartRepliesCardProps) {
  return (
    <PremiumCard className="flex h-full flex-col">
      <div className="mb-4 flex items-start justify-between">
        <div className="brand-icon-surface flex h-10 w-10 items-center justify-center rounded-xl">
          <MessageSquareReply className="h-5 w-5" />
        </div>
        <span className="text-xs font-semibold text-muted-foreground">03</span>
      </div>
      <h3 className="text-lg font-bold text-foreground">Smart Replies</h3>
      <p className="mt-1 text-sm font-medium text-muted-foreground">AI drafts in your voice</p>
      <div className="mt-5">
        <MetricPill label="generated" value={formatNumber(data.generatedCount)} />
      </div>
      {data.drafts.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {data.drafts.map((draft) => (
            <li key={draft.title}>
              <p className="truncate text-sm font-semibold text-brand-text">{draft.title}</p>
              <p className="truncate text-xs text-brand-muted">{draft.description}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-brand-muted">Generate a reply from any email.</p>
      )}
      <Button asChild className="mt-auto w-full gap-2 rounded-xl">
        <Link to={data.href} className="inline-flex w-full items-center justify-center gap-2">
          <span>Generate reply</span>
          <ArrowRight className="h-4 w-4 shrink-0" />
        </Link>
      </Button>
    </PremiumCard>
  );
}

interface FollowUpsCardProps {
  data: FollowUpsData;
}

export function FollowUpsCard({ data }: FollowUpsCardProps) {
  return (
    <PremiumCard className="flex h-full flex-col">
      <div className="mb-4 flex items-start justify-between">
        <div className="brand-icon-surface flex h-10 w-10 items-center justify-center rounded-xl">
          <Clock className="h-5 w-5" />
        </div>
        <span className="text-xs font-semibold text-muted-foreground">04</span>
      </div>
      <h3 className="text-lg font-bold text-foreground">Follow Ups &amp; Deadlines</h3>
      <p className="mt-1 text-sm font-medium text-muted-foreground">Stay ahead of what&apos;s due</p>
      <div className="mt-5">
        <MetricPill label="pending" value={formatNumber(data.pendingCount)} />
      </div>
      {data.items.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {data.items.map((item) => (
            <li key={item.title}>
              <p className="truncate text-sm font-semibold text-brand-text">{item.title}</p>
              <p className="truncate text-xs text-brand-muted">{item.description}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-brand-muted">No upcoming actions detected yet.</p>
      )}
    </PremiumCard>
  );
}
