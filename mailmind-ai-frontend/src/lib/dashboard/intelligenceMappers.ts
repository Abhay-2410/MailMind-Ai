import type { ActivityItem, DashboardResponse } from "@/types/dashboard";

export interface ImportantEmailsData {
  count: number;
  senders: string[];
  href: string;
}

export interface AISummariesData {
  todayCount: number;
  timeSavedMinutes: number;
  latestPreview: string | null;
}

export interface SmartRepliesData {
  generatedCount: number;
  drafts: { title: string; description: string }[];
  href: string;
}

export interface FollowUpItem {
  title: string;
  description: string;
  kind: "deadline" | "meeting" | "pending";
}

export interface FollowUpsData {
  items: FollowUpItem[];
  pendingCount: number;
}

function extractSender(description: string): string | null {
  const match = description.match(/from\s+([^·,]+)/i);
  return match ? match[1].trim() : null;
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

export function mapDashboardIntelligence(data: DashboardResponse) {
  const { stats, recent_activity } = data;

  const importantActivities = recent_activity.filter(
    (a) => a.type === "email_received" && /important/i.test(a.title + a.description),
  );

  const senders = [
    ...new Set(
      importantActivities
        .map((a) => extractSender(a.description) ?? a.title.split("·")[0]?.trim())
        .filter(Boolean) as string[],
    ),
  ].slice(0, 4);

  const summarizeToday = recent_activity.filter(
    (a) => a.type === "ai_summarize" && isToday(a.timestamp),
  );

  const replyActivities = recent_activity.filter((a) => a.type === "ai_reply");

  const followUpKeywords = /deadline|meeting|follow.?up|pending|reminder|due/i;
  const followItems: FollowUpItem[] = recent_activity
    .filter((a) => followUpKeywords.test(a.title + a.description))
    .slice(0, 4)
    .map((a) => ({
      title: a.title,
      description: a.description,
      kind: /meeting/i.test(a.title) ? "meeting" : /deadline|due/i.test(a.title) ? "deadline" : "pending",
    }));

  const important: ImportantEmailsData = {
    count: stats.important_emails,
    senders,
    href: "/inbox",
  };

  const summaries: AISummariesData = {
    todayCount: summarizeToday.length,
    timeSavedMinutes: Math.max(summarizeToday.length * 3, stats.ai_actions_saved * 2),
    latestPreview: summarizeToday[0]?.description ?? recent_activity.find((a) => a.type === "ai_summarize")?.description ?? null,
  };

  const replies: SmartRepliesData = {
    generatedCount: replyActivities.length || Math.floor(stats.ai_actions_saved / 3),
    drafts: replyActivities.slice(0, 3).map((a) => ({
      title: a.title,
      description: a.description,
    })),
    href: "/inbox",
  };

  const followUps: FollowUpsData = {
    items: followItems,
    pendingCount: Math.max(stats.unread_emails > 0 ? Math.min(5, stats.unread_emails) : 0, followItems.length),
  };

  return { important, summaries, replies, followUps };
}

export function groupRecentActivity(items: ActivityItem[]) {
  return {
    searches: items.filter((a) => a.type === "ai_search").slice(0, 5),
    summaries: items.filter((a) => a.type === "ai_summarize").slice(0, 5),
    aiActions: items
      .filter((a) => ["ai_reply", "ai_categorize", "ai_assistant", "inbox_sync"].includes(a.type))
      .slice(0, 5),
  };
}
