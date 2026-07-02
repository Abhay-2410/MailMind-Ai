import type { SmartCleanupCategoryConfig } from "@/types/cleanup";

export const SMART_CLEANUP_CATEGORIES: SmartCleanupCategoryConfig[] = [
  { id: "primary", label: "Primary Inbox", confidence: "HIGH" },
  { id: "promotions", label: "Promotions", confidence: "MEDIUM" },
  { id: "social_updates", label: "Social & Updates", confidence: "MEDIUM" },
  { id: "newsletters", label: "Newsletters", confidence: "MEDIUM" },
];

export const UNDO_WINDOW_MS = 5000;

/** Rough minutes saved estimate (5 seconds per email triaged manually). */
export function estimateMinutesSaved(emailCount: number): number {
  return Math.max(1, Math.round((emailCount * 5) / 60));
}
