import { AlertCircle, Calendar, CheckCircle2, ListChecks, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSummarizeEmail } from "@/hooks/useAI";
import { PRIORITY_LABELS, PRIORITY_STYLES, type SummarizeEmailResponse } from "@/types/ai";

interface AISummaryPanelProps {
  emailId: string;
}

export function AISummaryPanel({ emailId }: AISummaryPanelProps) {
  const summarizeMutation = useSummarizeEmail(emailId);
  const summary = summarizeMutation.data;

  return (
    <Card className="surface-card">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="h-5 w-5 text-brand-green" />
              AI Summary
            </CardTitle>
            <CardDescription>Get key points, action items, and priority at a glance</CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => summarizeMutation.mutate()}
            disabled={summarizeMutation.isPending}
          >
            {summarizeMutation.isPending ? "Summarizing…" : summary ? "Regenerate" : "Summarize"}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {summarizeMutation.isPending ? <SummarySkeleton /> : null}

        {summarizeMutation.isError ? (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{summarizeMutation.error.message || "Failed to generate summary."}</span>
          </div>
        ) : null}

        {!summarizeMutation.isPending && !summary ? (
          <p className="text-sm text-brand-muted">
            Click Summarize to analyze this email with AI.
          </p>
        ) : null}

        {summary ? <SummaryContent summary={summary} /> : null}
      </CardContent>
    </Card>
  );
}

function SummaryContent({ summary }: { summary: SummarizeEmailResponse }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          className={PRIORITY_STYLES[summary.priority_level]}
        >
          {PRIORITY_LABELS[summary.priority_level]} priority
        </Badge>
        <span className="text-xs text-brand-muted">via {summary.model_used}</span>
      </div>

      <p className="text-sm leading-relaxed text-brand-text">{summary.summary_text}</p>

      {summary.key_points.length > 0 ? (
        <SummarySection icon={ListChecks} title="Key points">
          <ul className="space-y-1.5">
            {summary.key_points.map((point) => (
              <li key={point} className="flex gap-2 text-sm text-brand-text">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-green" />
                {point}
              </li>
            ))}
          </ul>
        </SummarySection>
      ) : null}

      {summary.action_items.length > 0 ? (
        <SummarySection icon={CheckCircle2} title="Action items">
          <ul className="space-y-1.5">
            {summary.action_items.map((item) => (
              <li key={item} className="flex gap-2 text-sm text-brand-text">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-green" />
                {item}
              </li>
            ))}
          </ul>
        </SummarySection>
      ) : null}

      {summary.important_dates.length > 0 ? (
        <SummarySection icon={Calendar} title="Important dates">
          <ul className="space-y-1.5">
            {summary.important_dates.map((date) => (
              <li key={date} className="text-sm text-brand-text">
                {date}
              </li>
            ))}
          </ul>
        </SummarySection>
      ) : null}
    </div>
  );
}

function SummarySection({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof ListChecks;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-brand-text">
        <Icon className="h-4 w-4 text-brand-green" />
        {title}
      </h4>
      {children}
    </div>
  );
}

function SummarySkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
