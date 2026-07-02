import { RefreshCw } from "lucide-react";

import { SectionHeader } from "@/components/design-system";
import { Button } from "@/components/ui/button";
import { SYNC_BUTTON_LABEL } from "@/lib/navigation";

interface DashboardHeroProps {
  lastSynced: string | null;
  isSyncing: boolean;
  syncDetail?: string | null;
  onSync: () => void;
}

export function DashboardHero({ lastSynced, isSyncing, syncDetail, onSync }: DashboardHeroProps) {
  const statusLine = isSyncing
    ? syncDetail ?? "Syncing inbox…"
    : lastSynced
      ? `Last synced ${lastSynced}`
      : "Sync inbox to populate your workspace";

  return (
    <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
      <SectionHeader
        eyebrow="AI powered email workspace"
        title="Your Inbox, Organized by Intelligence"
        description="Summarize emails, generate replies, organize conversations and find anything instantly using AI."
      />
      <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
        <p className="text-sm font-medium text-muted-foreground">{statusLine}</p>
        <Button
          onClick={onSync}
          disabled={isSyncing}
          className="inline-flex min-w-[9.5rem] items-center justify-center gap-2 rounded-xl px-5 shadow-soft"
        >
          <RefreshCw className={`h-4 w-4 shrink-0 ${isSyncing ? "animate-spin" : ""}`} />
          <span>{isSyncing ? SYNC_BUTTON_LABEL.running : SYNC_BUTTON_LABEL.idle}</span>
        </Button>
      </div>
    </div>
  );
}
