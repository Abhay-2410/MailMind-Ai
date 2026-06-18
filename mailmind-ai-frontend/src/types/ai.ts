export type ReplyStyle = "professional" | "friendly" | "formal" | "short";

export type PriorityLevel = "low" | "medium" | "high" | "urgent";

export interface SummarizeEmailResponse {
  email_id: string;
  summary_text: string;
  key_points: string[];
  action_items: string[];
  important_dates: string[];
  priority_level: PriorityLevel;
  model_used: string;
}

export interface GenerateReplyResponse {
  email_id: string;
  reply: string;
  style: ReplyStyle;
  model_used: string;
}

export interface AssistantResponse {
  answer: string;
  model_used: string;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  model_used?: string;
  created_at: string;
  is_error?: boolean;
}

export const ASSISTANT_SUGGESTIONS = [
  "Summarize my unread emails",
  "Which emails need a reply?",
  "What deadlines do I have this week?",
  "Show me important emails from today",
] as const;

export const REPLY_STYLE_OPTIONS: { value: ReplyStyle; label: string }[] = [
  { value: "professional", label: "Professional" },
  { value: "friendly", label: "Friendly" },
  { value: "formal", label: "Formal" },
  { value: "short", label: "Short" },
];

export const PRIORITY_LABELS: Record<PriorityLevel, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

export const PRIORITY_STYLES: Record<PriorityLevel, string> = {
  low: "bg-slate-100 text-slate-600 border-slate-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  high: "bg-orange-50 text-orange-700 border-orange-200",
  urgent: "bg-red-50 text-red-700 border-red-200",
};
