import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Bot, Inbox, Mail, RefreshCw, Sparkles } from "lucide-react";

import { CategoryChart } from "@/components/dashboard/CategoryChart";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { StatCard } from "@/components/dashboard/StatCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/hooks/useDashboard";
import { syncInbox } from "@/hooks/useEmails";
import { formatNumber } from "@/lib/format";
import { staggerContainer, staggerItem } from "@/lib/motion";
import { useAuthStore } from "@/stores/authStore";

export function DashboardPage() {
  const queryClient = useQueryClient();
  const userEmail = useAuthStore((s) => s.user?.email);
  const isDemoUser = userEmail === "demo@example.com";
  const { data, isLoading, isError, refetch } = useDashboard();

  const syncMutation = useMutation({
    mutationFn: () => syncInbox({ syncAll: true, maxResults: 200 }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["inbox"] });
    },
  });

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (isError || !data) {
    return (
      <Card className="surface-card">
        <CardContent className="py-12 text-center">
          <p className="text-body">Unable to load dashboard data.</p>
          <Button className="mt-4" onClick={() => void refetch()}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { stats, categories, recent_activity } = data;
  const statCards = [
    { label: "Total Emails", value: formatNumber(stats.total_emails), icon: Mail },
    { label: "Unread", value: formatNumber(stats.unread_emails), icon: Inbox },
    { label: "Important", value: formatNumber(stats.important_emails), icon: Sparkles },
    { label: "AI Actions Saved", value: formatNumber(stats.ai_actions_saved), icon: Bot },
  ] as const;

  const lastSynced = stats.last_synced_at
    ? new Date(stats.last_synced_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="space-y-8">
      {isDemoUser ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="py-4 text-sm text-amber-900">
            You are signed in as the demo account. Sign in with Google to connect your Gmail inbox
            and sync your real emails.
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-body">
            {lastSynced ? `Last synced ${lastSynced}` : "Sync Gmail to populate your dashboard"}
          </p>
        </div>
        <Button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="shrink-0"
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
          {syncMutation.isPending ? "Syncing…" : "Sync Inbox"}
        </Button>
      </div>

      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        {statCards.map((stat) => (
          <motion.div key={stat.label} variants={staggerItem}>
            <StatCard label={stat.label} value={stat.value} icon={stat.icon} />
          </motion.div>
        ))}
      </motion.div>

      <div className="grid gap-6 lg:grid-cols-2">
        <CategoryChart categories={categories} />
        <RecentActivity items={recent_activity} />
      </div>

      {stats.total_emails === 0 ? (
        <Card className="surface-card border-dashed">
          <CardHeader>
            <CardTitle className="text-lg">Get started</CardTitle>
            <CardDescription>
              Connect your Gmail account and sync your inbox to unlock AI-powered insights.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
              Sync Gmail now
            </Button>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-32 rounded-2xl" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    </div>
  );
}
