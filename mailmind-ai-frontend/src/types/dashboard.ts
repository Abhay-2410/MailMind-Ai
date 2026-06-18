export interface DashboardStats {
  total_emails: number;
  unread_emails: number;
  important_emails: number;
  ai_actions_saved: number;
  categorized_emails: number;
  last_synced_at: string | null;
}

export interface CategoryStat {
  category: string;
  label: string;
  count: number;
  percentage: number;
}

export type ActivityType =
  | "email_received"
  | "ai_summarize"
  | "ai_reply"
  | "ai_categorize"
  | "ai_search"
  | "ai_assistant"
  | "inbox_sync";

export interface ActivityItem {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  timestamp: string;
}

export interface DashboardResponse {
  stats: DashboardStats;
  categories: CategoryStat[];
  recent_activity: ActivityItem[];
}
