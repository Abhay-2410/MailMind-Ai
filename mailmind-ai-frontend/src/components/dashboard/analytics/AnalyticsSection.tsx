import { motion } from "framer-motion";
import { Bot, Clock, Inbox, Mail, Sparkles } from "lucide-react";

import { PremiumCard } from "@/components/design-system";
import { CategoryChart } from "@/components/dashboard/CategoryChart";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { formatNumber } from "@/lib/format";
import { staggerContainer, staggerItem } from "@/lib/motion";
import type { CategoryStat, DashboardStats, ActivityItem } from "@/types/dashboard";

interface AnalyticsSectionProps {
  stats: DashboardStats;
  categories: CategoryStat[];
  recentActivity: ActivityItem[];
}

export function AnalyticsSection({ stats, categories, recentActivity }: AnalyticsSectionProps) {
  const timeSavedMinutes = Math.max(stats.ai_actions_saved * 2, 0);

  const metrics = [
    { label: "Total Emails", value: formatNumber(stats.total_emails), icon: Mail },
    { label: "Unread", value: formatNumber(stats.unread_emails), icon: Inbox },
    { label: "Important", value: formatNumber(stats.important_emails), icon: Sparkles },
    { label: "AI Actions Saved", value: formatNumber(stats.ai_actions_saved), icon: Bot },
    { label: "Time Saved", value: `${formatNumber(timeSavedMinutes)}m`, icon: Clock },
  ] as const;

  return (
    <section className="space-y-6">
      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
      >
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <motion.div key={metric.label} variants={staggerItem}>
              <PremiumCard interactive className="p-5">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-brand-muted">
                    {metric.label}
                  </p>
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-green-soft">
                    <Icon className="h-4 w-4 text-brand-green" />
                  </div>
                </div>
                <p className="mt-3 text-2xl font-bold tabular-nums text-brand-text">{metric.value}</p>
              </PremiumCard>
            </motion.div>
          );
        })}
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-2">
        <CategoryChart categories={categories} totalEmails={stats.total_emails} />
        <RecentActivity items={recentActivity} />
      </div>
    </section>
  );
}
