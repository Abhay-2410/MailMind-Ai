import { Link } from "react-router-dom";
import { Star } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { CATEGORY_BADGE_STYLES, getCategoryLabel } from "@/lib/emailCategories";
import { formatEmailDate, getSenderInitials } from "@/lib/format";
import { ROUTES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { EmailListItem as EmailListItemType } from "@/types/email";

interface EmailListItemProps {
  email: EmailListItemType;
}

export function EmailListItem({ email }: EmailListItemProps) {
  const displayName = email.sender_name?.trim() || email.sender;
  const categoryLabel = getCategoryLabel(email.category);

  return (
    <Link
      to={`${ROUTES.EMAIL}/${email.id}`}
      className={cn(
        "group flex gap-3 border-b border-border px-4 py-4 transition-colors hover:bg-accent/60 sm:gap-4 sm:px-5",
        !email.is_read && "bg-brand-green-soft/30",
      )}
    >
      <Avatar className="h-10 w-10">
        <AvatarFallback className="bg-brand-green-soft text-xs font-semibold text-brand-green">
          {getSenderInitials(email.sender_name, email.sender)}
        </AvatarFallback>
      </Avatar>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p
                className={cn(
                  "truncate text-sm text-brand-text",
                  !email.is_read ? "font-semibold" : "font-medium",
                )}
              >
                {displayName}
              </p>
              {email.is_starred ? (
                <Star className="h-3.5 w-3.5 shrink-0 fill-amber-400 text-amber-400" />
              ) : null}
              {email.is_important ? (
                <Badge className="hidden border-0 bg-brand-green-soft px-2 py-0 text-[10px] text-brand-green sm:inline-flex">
                  Important
                </Badge>
              ) : null}
            </div>
            <p
              className={cn(
                "mt-0.5 truncate text-sm",
                !email.is_read ? "font-medium text-brand-text" : "text-brand-text",
              )}
            >
              {email.subject || "(No subject)"}
            </p>
          </div>
          <time className="shrink-0 text-xs text-brand-muted">{formatEmailDate(email.received_at)}</time>
        </div>

        <div className="mt-1 flex items-center justify-between gap-3">
          <p className="truncate text-sm text-brand-muted">{email.preview || "No preview available"}</p>
          {categoryLabel ? (
            <Badge
              variant="outline"
              className={cn(
                "hidden shrink-0 capitalize sm:inline-flex",
                CATEGORY_BADGE_STYLES[email.category ?? ""] ?? "bg-accent text-brand-text",
              )}
            >
              {categoryLabel}
            </Badge>
          ) : null}
        </div>
      </div>
    </Link>
  );
}
