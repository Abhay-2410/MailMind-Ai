import { motion } from "framer-motion";

import { PremiumCard } from "@/components/design-system";
import { Button } from "@/components/ui/button";
import { fadeUp } from "@/lib/motion";

interface DashboardEmptyStateProps {
  onSync: () => void;
  isSyncing: boolean;
}

export function DashboardEmptyState({ onSync, isSyncing }: DashboardEmptyStateProps) {
  return (
    <motion.div variants={fadeUp} initial="initial" animate="animate">
      <PremiumCard interactive={false} className="border border-dashed border-brand-green/20 bg-brand-green-soft/20">
        <h3 className="text-lg font-bold text-brand-text">Connect your Gmail workspace</h3>
        <p className="mt-2 max-w-lg text-sm font-medium text-brand-muted">
          Sync your inbox to unlock AI summaries, smart replies, intelligence cards, and natural
          language search.
        </p>
        <Button className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl" onClick={onSync} disabled={isSyncing}>
          <span>{isSyncing ? "Syncing…" : "Sync inbox"}</span>
        </Button>
      </PremiumCard>
    </motion.div>
  );
}
