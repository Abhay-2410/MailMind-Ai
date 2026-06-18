import type { EmailListItem } from "@/types/email";

export interface SearchResponse {
  natural_query: string;
  gmail_query: string;
  explanation: string;
  model_used: string;
  results: EmailListItem[];
  total: number;
}

export interface SearchHistoryItem {
  id: string;
  natural_query: string;
  gmail_query: string;
  results_count: number;
  model_used: string | null;
  created_at: string;
}

export const SEARCH_SUGGESTIONS = [
  "Show unread Amazon emails",
  "Find internship emails",
  "Emails received this week",
  "Meeting requests from professors",
] as const;
