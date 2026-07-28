import { motion } from "framer-motion";
import { BarChart3, Bot, Inbox, Mail, Sparkles, Tags } from "lucide-react";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { EmailList } from "@/components/inbox/EmailList";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { PremiumCard } from "@/components/design-system";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useInbox } from "@/hooks/useEmails";
import { CATEGORY_BADGE_STYLES, EMAIL_CATEGORY_OPTIONS, getCategoryLabel } from "@/lib/emailCategories";
import { formatNumber } from "@/lib/format";
import { staggerContainer, staggerItem } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { EmailCategoryFilter } from "@/stores/inboxStore";
import { useInboxStore } from "@/stores/inboxStore";
import type { ActivityItem, CategoryStat, DashboardStats } from "@/types/dashboard";

const CATEGORY_BAR_COLORS: Record<string, string> = {
  important: "bg-brand-green",
  work: "bg-brand-green-light",
  personal: "bg-stone-500",
  finance: "bg-emerald-700/80",
  promotions: "bg-stone-400",
  social: "bg-stone-600",
  updates: "bg-amber-700/70",
  uncategorized: "bg-stone-300",
};

const CATEGORY_TILE_GRADIENTS: Record<string, string> = {
  important: "from-[hsl(48_35%_93%)] to-[hsl(48_28%_88%)] border-border",
  work: "from-[hsl(48_30%_92%)] to-[hsl(45_22%_88%)] border-border",
  personal: "from-[hsl(40_25%_92%)] to-[hsl(48_28%_90%)] border-border",
  finance: "from-[hsl(155_18%_90%)] to-[hsl(48_28%_90%)] border-border",
  promotions: "from-[hsl(40_15%_92%)] to-[hsl(48_20%_90%)] border-border",
  social: "from-[hsl(48_28%_91%)] to-[hsl(40_18%_88%)] border-border",
  updates: "from-[hsl(42_30%_91%)] to-[hsl(48_28%_90%)] border-border",
};

interface CategoryInsightsSectionProps {
  stats: DashboardStats;
  categories: CategoryStat[];
  recentActivity: ActivityItem[];
}

function parseCategoryParam(value: string | null): EmailCategoryFilter | null {
  if (!value || value === "all") return null;
  const valid = EMAIL_CATEGORY_OPTIONS.some((o) => o.value === value);
  return valid ? (value as EmailCategoryFilter) : null;
}

export function CategoryInsightsSection({
  stats,
  categories,
  recentActivity,
}: CategoryInsightsSectionProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedCategory = parseCategoryParam(searchParams.get("category"));
  const { page, setPage, setCategory } = useInboxStore();

  const inboxQuery = useInbox({ enabled: Boolean(selectedCategory) });

  useEffect(() => {
    if (selectedCategory) {
      setCategory(selectedCategory);
      setPage(1);
    }
  }, [selectedCategory, setCategory, setPage]);

  function selectCategory(category: EmailCategoryFilter | null) {
    const next = new URLSearchParams(searchParams);
    next.set("section", "insights");
    if (category) {
      next.set("category", category);
    } else {
      next.delete("category");
    }
    setSearchParams(next, { replace: true });
  }

  const metrics = [
    { label: "Total Emails", value: formatNumber(stats.total_emails), icon: Mail },
    { label: "Unread", value: formatNumber(stats.unread_emails), icon: Inbox },
    { label: "Important", value: formatNumber(stats.important_emails), icon: Sparkles },
    { label: "AI Actions", value: formatNumber(stats.ai_actions_saved), icon: Bot },
  ] as const;

  const categoryRows = categories.filter((c) => c.count > 0);
  const browseLabel = selectedCategory ? getCategoryLabel(selectedCategory) : null;

  return (
    <section className="space-y-8">
      <div className="surface-panel bg-gradient-to-r from-card via-brand-green-soft/30 to-card px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl brand-icon-surface">
            <BarChart3 className="h-5 w-5 text-brand-green" />
          </div>
          <div>
            <p className="text-sm font-bold text-foreground">Category Insights</p>
            <p className="text-sm text-muted-foreground">
              Analyze how your inbox is distributed, then drill into any category to browse emails.
            </p>
          </div>
        </div>
      </div>

      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <motion.div key={metric.label} variants={staggerItem}>
              <PremiumCard className="p-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-brand-muted">
                    {metric.label}
                  </p>
                  <Icon className="h-4 w-4 text-brand-green" />
                </div>
                <p className="mt-2 text-2xl font-bold tabular-nums text-brand-text">{metric.value}</p>
              </PremiumCard>
            </motion.div>
          );
        })}
      </motion.div>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="surface-card xl:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Distribution</CardTitle>
            <CardDescription>Share of synced emails by AI category</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {categoryRows.length === 0 ? (
              <p className="py-6 text-center text-sm text-brand-muted">
                Sync your inbox to see category distribution.
              </p>
            ) : (
              categoryRows.map((item, index) => (
                <motion.button
                  key={item.category}
                  type="button"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.04 }}
                  onClick={() => selectCategory(item.category as EmailCategoryFilter)}
                  className={cn(
                    "w-full rounded-xl border border-transparent p-2 text-left transition-all hover:bg-accent/50",
                    selectedCategory === item.category && "border-brand-green/30 bg-brand-green-soft/40",
                  )}
                >
                  <div className="mb-1.5 flex items-center justify-between text-sm">
                    <span className="font-medium text-brand-text">{item.label}</span>
                    <span className="text-brand-muted">
                      {item.count} · {item.percentage}%
                    </span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        CATEGORY_BAR_COLORS[item.category] ?? "bg-brand-green",
                      )}
                      style={{ width: `${Math.min(item.percentage, 100)}%` }}
                    />
                  </div>
                </motion.button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="surface-card xl:col-span-3">
          <CardHeader className="flex flex-row items-start justify-between gap-3">
            <div>
              <CardTitle className="text-lg">Browse by category</CardTitle>
              <CardDescription>Click a category to load matching emails below</CardDescription>
            </div>
            {selectedCategory ? (
              <Button type="button" size="sm" variant="outline" onClick={() => selectCategory(null)}>
                Clear selection
              </Button>
            ) : null}
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {EMAIL_CATEGORY_OPTIONS.filter((o) => o.value !== "all").map((option) => {
                const stat = categories.find((c) => c.category === option.value);
                const count = stat?.count ?? 0;
                const active = selectedCategory === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => selectCategory(option.value)}
                    className={cn(
                      "rounded-2xl border bg-gradient-to-br p-4 text-left transition-all",
                      CATEGORY_TILE_GRADIENTS[option.value] ?? "from-card to-muted border-border",
                      active && "ring-2 ring-brand-green/40 shadow-soft",
                      count === 0 && "opacity-55",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-brand-text">{option.label}</span>
                      <Tags className="h-4 w-4 shrink-0 text-brand-green" />
                    </div>
                    <p className="mt-1 text-2xl font-bold tabular-nums text-brand-text">
                      {formatNumber(count)}
                    </p>
                    <p className="mt-1 text-xs text-brand-muted">
                      {stat ? `${stat.percentage}% of inbox` : "No emails yet"}
                    </p>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      <div>
        {selectedCategory ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-brand-text">
                Browsing{" "}
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-bold uppercase",
                    CATEGORY_BADGE_STYLES[selectedCategory] ?? "bg-accent text-brand-text",
                  )}
                >
                  {browseLabel}
                </span>{" "}
                emails
              </p>
            </div>
            <EmailList
              data={inboxQuery.data}
              isLoading={inboxQuery.isLoading}
              isFetching={inboxQuery.isFetching}
              isError={inboxQuery.isError}
              onRetry={() => void inboxQuery.refetch()}
              page={page}
              onPageChange={setPage}
            />
          </div>
        ) : (
          <RecentActivity items={recentActivity} />
        )}
      </div>
    </section>
  );
}
