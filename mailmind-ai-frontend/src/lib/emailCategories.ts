import type { EmailCategoryFilter } from "@/stores/inboxStore";

export const EMAIL_CATEGORY_OPTIONS: { value: EmailCategoryFilter; label: string }[] = [
  { value: "all", label: "All categories" },
  { value: "important", label: "Important" },
  { value: "work", label: "Work" },
  { value: "personal", label: "Personal" },
  { value: "finance", label: "Finance" },
  { value: "promotions", label: "Promotions" },
  { value: "social", label: "Social" },
  { value: "updates", label: "Updates" },
];

export const CATEGORY_BADGE_STYLES: Record<string, string> = {
  important: "bg-brand-green-soft text-brand-green border-border",
  work: "bg-secondary text-brand-text border-border",
  personal: "bg-card text-brand-muted border-border",
  finance: "bg-[hsl(155_18%_90%)] text-brand-text border-border",
  promotions: "bg-muted text-brand-muted border-border",
  social: "bg-secondary text-brand-muted border-border",
  updates: "bg-[hsl(42_30%_90%)] text-brand-text border-border",
};

export function getCategoryLabel(category: string | null): string | null {
  if (!category) return null;
  return EMAIL_CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? category;
}
