import { useEffect, useMemo, useState } from "react";
import { FileText, Globe, Star } from "lucide-react";

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
  const hasHtmlBody = Boolean(email.body_html?.trim());
  const textFallback = useMemo(
    () => buildTextFallback(email.body_text, email.preview, email.body_html),
    [email.body_html, email.body_text, email.preview],
  );
  const [bodyMode, setBodyMode] = useState<"text" | "html">(hasHtmlBody && textFallback ? "text" : "html");

  useEffect(() => {
    setBodyMode(hasHtmlBody && textFallback ? "text" : "html");
  }, [email.id, hasHtmlBody, textFallback]);

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
        {hasHtmlBody && textFallback ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-6">
            <p className="text-xs font-medium uppercase tracking-wide text-brand-muted">Message view</p>
            <div className="flex w-full gap-2 sm:w-auto">
              <button
                type="button"
                onClick={() => setBodyMode("text")}
                className={cn(
                  "inline-flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors sm:flex-initial",
                  bodyMode === "text"
                    ? "border-brand-green/40 bg-brand-green-soft text-brand-green"
                    : "border-border text-brand-muted hover:bg-accent hover:text-brand-text",
                )}
              >
                <FileText className="h-4 w-4" />
                Readable text
              </button>
              <button
                type="button"
                onClick={() => setBodyMode("html")}
                className={cn(
                  "inline-flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors sm:flex-initial",
                  bodyMode === "html"
                    ? "border-brand-green/40 bg-brand-green-soft text-brand-green"
                    : "border-border text-brand-muted hover:bg-accent hover:text-brand-text",
                )}
              >
                <Globe className="h-4 w-4" />
                Original HTML
              </button>
            </div>
          </div>
        ) : null}
        <EmailBody
          bodyText={bodyMode === "text" ? textFallback : email.body_text}
          bodyHtml={bodyMode === "html" ? email.body_html : null}
          preview={email.preview}
        />
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
        className="min-h-[420px] w-full border-0 bg-white"
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
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
    html { background: #ffffff; }
    body { font-family: system-ui, sans-serif; font-size: 14px; line-height: 1.6; color: #1D2939; margin: 16px; overflow-wrap: anywhere; word-break: break-word; }
    img { max-width: 100%; height: auto; }
    table { max-width: 100% !important; width: 100% !important; display: block; overflow-x: auto; }
    pre, code { white-space: pre-wrap; overflow-wrap: anywhere; }
    a { color: #6BAF92; }
  </style></head><body>${html}</body></html>`;
}

function buildTextFallback(
  bodyText: string | null,
  preview: string | null,
  bodyHtml: string | null,
): string | null {
  const text = bodyText?.trim();
  if (text) return text;

  const html = bodyHtml?.trim();
  if (html) {
    const stripped = html
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(p|div|li|tr|h[1-6])>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/gi, " ")
      .replace(/&amp;/gi, "&")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/\r/g, "")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
    if (stripped) return stripped;
  }

  return preview?.trim() || null;
}
