import type { EmailCategoryFilter } from "@/stores/inboxStore";

/** Content categories. "Important" is a separate priority flag (is_priority), not a category. */
export const EMAIL_CATEGORY_OPTIONS: { value: EmailCategoryFilter; label: string }[] = [
  { value: "all", label: "All categories" },
  { value: "work", label: "Work" },
  { value: "personal", label: "Personal" },
  { value: "finance", label: "Finance" },
  { value: "promotions", label: "Promotions" },
  { value: "social", label: "Social" },
  { value: "updates", label: "Updates" },
];

export const ASSIGNABLE_CATEGORIES = EMAIL_CATEGORY_OPTIONS.filter((option) => option.value !== "all");

export const CATEGORY_BADGE_STYLES: Record<string, string> = {
  important: "bg-brand-green-soft text-brand-green border-border",
  work: "bg-secondary text-brand-text border-border",
  personal: "bg-card text-brand-muted border-border",
  finance: "bg-[hsl(155_18%_90%)] text-brand-text border-border",
  promotions: "bg-muted text-brand-muted border-border",
  social: "bg-secondary text-brand-muted border-border",
  updates: "bg-[hsl(42_30%_90%)] text-brand-text border-border",
};

const CATEGORY_SOURCE_LABELS: Record<string, string> = {
  user: "Set by you",
  sender_rule: "Your rule for this sender",
  rule: "Rule",
  sender_history: "Sender history",
  thread: "Same conversation",
  ai: "AI",
  gmail: "Gmail tab",
};

export function getCategoryLabel(category: string | null): string | null {
  if (!category) return null;
  if (category === "important") return "Important";
  return EMAIL_CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? category;
}

export function getCategorySourceLabel(source: string | null | undefined): string | null {
  if (!source) return null;
  return CATEGORY_SOURCE_LABELS[source] ?? source;
}
