import { ArrowRight, Mail, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { MetricPill, PremiumCard } from "@/components/design-system";
import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/format";
import type { ImportantEmailsData } from "@/lib/dashboard/intelligenceMappers";

interface ImportantEmailsCardProps {
  data: ImportantEmailsData;
}

export function ImportantEmailsCard({ data }: ImportantEmailsCardProps) {
  return (
    <PremiumCard className="flex h-full flex-col">
      <div className="mb-4 flex items-start justify-between">
        <div className="brand-icon-surface flex h-10 w-10 items-center justify-center rounded-xl">
          <Mail className="h-5 w-5" />
        </div>
        <span className="text-xs font-semibold text-muted-foreground">01</span>
      </div>
      <h3 className="text-lg font-bold text-foreground">Today&apos;s Important Emails</h3>
      <p className="mt-1 text-sm font-medium text-muted-foreground">Priority messages needing attention</p>
      <div className="mt-5">
        <MetricPill label="important" value={formatNumber(data.count)} />
      </div>
      {data.senders.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {data.senders.map((sender) => (
            <li key={sender} className="truncate text-sm font-medium text-brand-text">
              {sender}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-brand-muted">No important senders yet — sync your inbox.</p>
      )}
      <Button asChild variant="outline" className="mt-auto w-full gap-2 rounded-xl">
        <Link to={data.href} className="inline-flex w-full items-center justify-center gap-2">
          <span>Open inbox</span>
          <ArrowRight className="h-4 w-4 shrink-0" />
        </Link>
      </Button>
    </PremiumCard>
  );
}

interface AISummariesCardProps {
  data: import("@/lib/dashboard/intelligenceMappers").AISummariesData;
}

export function AISummariesCard({ data }: AISummariesCardProps) {
  return (
    <PremiumCard className="flex h-full flex-col">
      <div className="mb-4 flex items-start justify-between">
        <div className="brand-icon-surface flex h-10 w-10 items-center justify-center rounded-xl">
          <Sparkles className="h-5 w-5" />
        </div>
        <span className="text-xs font-semibold text-muted-foreground">02</span>
      </div>
      <h3 className="text-lg font-bold text-foreground">AI Summaries</h3>
      <p className="mt-1 text-sm font-medium text-muted-foreground">Instant clarity for long threads</p>
      <div className="mt-5 flex flex-wrap gap-2">
        <MetricPill label="today" value={formatNumber(data.todayCount)} />
        <MetricPill label="mins saved" value={formatNumber(data.timeSavedMinutes)} />
      </div>
      {data.latestPreview ? (
        <p className="mt-4 line-clamp-3 text-sm leading-relaxed text-brand-muted">
          {data.latestPreview}
        </p>
      ) : (
        <p className="mt-4 text-sm text-brand-muted">Summarize an email to see insights here.</p>
      )}
    </PremiumCard>
  );
}
