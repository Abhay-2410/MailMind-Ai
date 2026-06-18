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
  important: "bg-brand-green-soft text-brand-green border-brand-green/20",
  work: "bg-emerald-50 text-emerald-700 border-emerald-200",
  personal: "bg-violet-50 text-violet-700 border-violet-200",
  finance: "bg-teal-50 text-teal-700 border-teal-200",
  promotions: "bg-slate-100 text-slate-600 border-slate-200",
  social: "bg-violet-50 text-violet-600 border-violet-200",
  updates: "bg-amber-50 text-amber-700 border-amber-200",
};

export function getCategoryLabel(category: string | null): string | null {
  if (!category) return null;
  return EMAIL_CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? category;
}
