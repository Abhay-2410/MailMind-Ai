import { Star } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { CATEGORY_BADGE_STYLES, getCategoryLabel } from "@/lib/emailCategories";
import { formatEmailDate, getSenderInitials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EmailDetail } from "@/types/email";

interface EmailReaderProps {
  email: EmailDetail;
}

export function EmailReader({ email }: EmailReaderProps) {
  const displayName = email.sender_name?.trim() || email.sender;
  const categoryLabel = getCategoryLabel(email.category);

  return (
    <Card className="surface-card overflow-hidden">
      <CardHeader className="space-y-4 pb-4">
        <div className="flex flex-wrap items-center gap-2">
          {email.is_important ? (
            <Badge className="border-0 bg-brand-green-soft text-brand-green">Important</Badge>
          ) : null}
          {email.is_starred ? (
            <Badge variant="outline" className="gap-1 border-amber-200 bg-amber-50 text-amber-700">
              <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
              Starred
            </Badge>
          ) : null}
          {categoryLabel ? (
            <Badge
              variant="outline"
              className={cn(
                "capitalize",
                CATEGORY_BADGE_STYLES[email.category ?? ""] ?? "bg-accent text-brand-text",
              )}
            >
              {categoryLabel}
            </Badge>
          ) : null}
          {!email.is_read ? (
            <Badge variant="outline" className="border-brand-green/30 bg-brand-green-soft text-brand-green">
              Unread
            </Badge>
          ) : null}
        </div>

        <div>
          <h1 className="text-xl font-semibold text-brand-text sm:text-2xl">
            {email.subject || "(No subject)"}
          </h1>
          <div className="mt-4 flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-green-soft text-sm font-semibold text-brand-green">
              {getSenderInitials(email.sender_name, email.sender)}
            </div>
            <div className="min-w-0">
              <p className="font-medium text-brand-text">{displayName}</p>
              <p className="truncate text-sm text-brand-muted">{email.sender}</p>
              <time className="text-sm text-brand-muted">{formatEmailDate(email.received_at)}</time>
            </div>
          </div>
        </div>
      </CardHeader>

      <Separator />

      <CardContent className="p-0">
        <EmailBody bodyText={email.body_text} bodyHtml={email.body_html} preview={email.preview} />
      </CardContent>

      {email.labels.length > 0 ? (
        <>
          <Separator />
          <CardContent className="flex flex-wrap gap-2 py-4">
            {email.labels.map((label) => (
              <Badge key={label} variant="secondary" className="font-normal">
                {label}
              </Badge>
            ))}
          </CardContent>
        </>
      ) : null}
    </Card>
  );
}

function EmailBody({
  bodyText,
  bodyHtml,
  preview,
}: {
  bodyText: string | null;
  bodyHtml: string | null;
  preview: string | null;
}) {
  if (bodyHtml) {
    return (
      <iframe
        title="Email content"
        sandbox=""
        srcDoc={wrapEmailHtml(bodyHtml)}
        className="min-h-[320px] w-full border-0 bg-white"
      />
    );
  }

  const text = bodyText || preview;
  if (!text) {
    return <p className="px-6 py-8 text-center text-brand-muted">No email content available.</p>;
  }

  return (
    <div className="whitespace-pre-wrap px-6 py-6 text-sm leading-relaxed text-brand-text">{text}</div>
  );
}

function wrapEmailHtml(html: string): string {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    body { font-family: system-ui, sans-serif; font-size: 14px; line-height: 1.6; color: #1D2939; margin: 24px; }
    img { max-width: 100%; height: auto; }
    a { color: #6BAF92; }
  </style></head><body>${html}</body></html>`;
}
