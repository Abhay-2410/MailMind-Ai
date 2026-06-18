import { AlertCircle, Check, Copy, MessageSquare } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useGenerateReply } from "@/hooks/useAI";
import { cn } from "@/lib/utils";
import { REPLY_STYLE_OPTIONS, type ReplyStyle } from "@/types/ai";

interface ReplyGeneratorProps {
  emailId: string;
}

export function ReplyGenerator({ emailId }: ReplyGeneratorProps) {
  const [style, setStyle] = useState<ReplyStyle>("professional");
  const [copied, setCopied] = useState(false);
  const replyMutation = useGenerateReply(emailId);

  async function handleCopy() {
    if (!replyMutation.data?.reply) return;
    await navigator.clipboard.writeText(replyMutation.data.reply);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Card className="surface-card">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <MessageSquare className="h-5 w-5 text-brand-green" />
              AI Reply
            </CardTitle>
            <CardDescription>Generate a draft reply in your preferred tone</CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => replyMutation.mutate(style)}
            disabled={replyMutation.isPending}
          >
            {replyMutation.isPending ? "Generating…" : "Generate"}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {REPLY_STYLE_OPTIONS.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={style === option.value ? "default" : "outline"}
              onClick={() => setStyle(option.value)}
              className={cn(
                "rounded-full",
                style !== option.value && "bg-white hover:bg-accent",
              )}
            >
              {option.label}
            </Button>
          ))}
        </div>

        {replyMutation.isPending ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : null}

        {replyMutation.isError ? (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{replyMutation.error.message || "Failed to generate reply."}</span>
          </div>
        ) : null}

        {!replyMutation.isPending && !replyMutation.data ? (
          <p className="text-sm text-brand-muted">
            Choose a tone and click Generate to draft a reply.
          </p>
        ) : null}

        {replyMutation.data ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-border bg-accent/40 p-4">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-brand-text">
                {replyMutation.data.reply}
              </p>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs text-brand-muted">via {replyMutation.data.model_used}</span>
              <Button type="button" variant="outline" size="sm" onClick={() => void handleCopy()}>
                {copied ? (
                  <>
                    <Check className="mr-2 h-4 w-4 text-brand-green" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="mr-2 h-4 w-4" />
                    Copy reply
                  </>
                )}
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
