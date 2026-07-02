import { motion } from "framer-motion";
import { useSearchParams } from "react-router-dom";

import { CategoryInsightsSection } from "@/components/dashboard/insights/CategoryInsightsSection";
import { DashboardCommandCenter } from "@/components/dashboard/DashboardCommandCenter";
import { DashboardEmptyState } from "@/components/dashboard/DashboardEmptyState";
import { DashboardHero } from "@/components/dashboard/DashboardHero";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { IntelligenceGrid } from "@/components/dashboard/intelligence/IntelligenceGrid";
import { SmartCleanupPanel } from "@/components/dashboard/SmartCleanupPanel";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useDashboardIntelligence } from "@/hooks/useDashboardIntelligence";
import { useDashboard } from "@/hooks/useDashboard";
import { useAutoSync } from "@/hooks/useAutoSync";
import { formatSyncProgress } from "@/lib/navigation";
import { fadeUp } from "@/lib/motion";
import { useAuthStore } from "@/stores/authStore";

export function DashboardPageContent() {
  const [searchParams] = useSearchParams();
  const isInsightsView = searchParams.get("section") === "insights";
  const userEmail = useAuthStore((s) => s.user?.email);
  const isDemoUser = userEmail === "demo@example.com";
  const { data, isLoading, isError, refetch } = useDashboard();
  const intelligence = useDashboardIntelligence(data);
  const { isSyncing, syncStatus, triggerFullSync } = useAutoSync();

  if (isLoading) {
    return <DashboardSkeleton />;
  }

  if (isError || !data || !intelligence) {
    return (
      <Card className="surface-card">
        <CardContent className="py-12 text-center">
          <p className="text-body">Unable to load dashboard data.</p>
          <Button className="mt-4 rounded-xl" onClick={() => void refetch()}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const lastSynced = data.stats.last_synced_at
    ? new Date(data.stats.last_synced_at).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  if (isInsightsView) {
    return (
      <motion.div variants={fadeUp} initial="initial" animate="animate">
        <CategoryInsightsSection
          stats={data.stats}
          categories={data.categories}
          recentActivity={data.recent_activity}
        />
      </motion.div>
    );
  }

  return (
    <motion.div
      variants={fadeUp}
      initial="initial"
      animate="animate"
      className="space-y-10"
    >
      {isDemoUser ? (
        <Card className="border-amber-200/80 bg-amber-50/90 shadow-sm dark:border-amber-500/25 dark:bg-amber-950/35">
          <CardContent className="py-4 text-sm font-medium text-amber-900 dark:text-amber-100">
            You are signed in as the demo account. Sign in with Google to connect your Gmail inbox.
          </CardContent>
        </Card>
      ) : null}

      <DashboardHero
        lastSynced={lastSynced}
        isSyncing={isSyncing}
        syncDetail={
          syncStatus?.status === "running"
            ? formatSyncProgress(syncStatus.fetched_count, syncStatus.new_count)
            : null
        }
        onSync={triggerFullSync}
      />

      <DashboardCommandCenter />

      <IntelligenceGrid
        important={intelligence.important}
        summaries={intelligence.summaries}
        replies={intelligence.replies}
        followUps={intelligence.followUps}
      />

      <SmartCleanupPanel />

      {data.stats.total_emails === 0 ? (
        <DashboardEmptyState onSync={triggerFullSync} isSyncing={isSyncing} />
      ) : null}
    </motion.div>
  );
}
