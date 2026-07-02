import { formatDistanceToNow } from "@/lib/format";
import {
  Bot,
  Inbox,
  Mail,
  MessageSquare,
  RefreshCw,
  Search,
  Sparkles,
  Tag,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ActivityItem, ActivityType } from "@/types/dashboard";

const ACTIVITY_ICONS: Record<ActivityType, typeof Mail> = {
  email_received: Mail,
  ai_summarize: Sparkles,
  ai_reply: MessageSquare,
  ai_categorize: Tag,
  ai_search: Search,
  ai_assistant: Bot,
  inbox_sync: RefreshCw,
};

const ACTIVITY_COLORS: Record<ActivityType, string> = {
  email_received: "bg-brand-green-soft text-brand-green",
  ai_summarize: "bg-brand-green-soft text-brand-green",
  ai_reply: "bg-brand-green-soft text-brand-green",
  ai_categorize: "bg-brand-green-soft text-brand-green",
  ai_search: "bg-brand-green-soft text-brand-green",
  ai_assistant: "bg-brand-green-soft text-brand-green",
  inbox_sync: "bg-accent text-foreground",
};

interface RecentActivityProps {
  items: ActivityItem[];
}

export function RecentActivity({ items }: RecentActivityProps) {
  return (
    <Card className="surface-card h-full">
      <CardHeader>
        <CardTitle className="text-lg">Recent Activity</CardTitle>
        <CardDescription>Latest emails and AI actions</CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="py-8 text-center text-body">
            No activity yet. Connect Gmail and sync your inbox to get started.
          </p>
        ) : (
          <ul className="space-y-4">
            {items.map((item) => {
              const Icon = ACTIVITY_ICONS[item.type] ?? Inbox;
              return (
                <li key={`${item.type}-${item.id}`} className="flex gap-3">
                  <div
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${ACTIVITY_COLORS[item.type]}`}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{item.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{item.description}</p>
                  </div>
                  <time className="shrink-0 text-xs text-muted-foreground">
                    {formatDistanceToNow(item.timestamp)}
                  </time>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
