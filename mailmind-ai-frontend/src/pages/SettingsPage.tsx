import { Settings as SettingsIcon } from "lucide-react";

import { AIModelSettings } from "@/components/settings/AIModelSettings";
import { GmailAccounts } from "@/components/settings/GmailAccounts";
import { ProfileSettings } from "@/components/settings/ProfileSettings";
import { SecuritySettings } from "@/components/settings/SecuritySettings";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSettings } from "@/hooks/useSettings";

export function SettingsPage() {
  const { data, isLoading, isError, refetch } = useSettings();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-48 rounded-2xl" />
        <Skeleton className="h-48 rounded-2xl" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        icon={SettingsIcon}
        title="Unable to load settings"
        description="Something went wrong while fetching your preferences."
        action={
          <Button onClick={() => void refetch()} variant="outline">
            Try again
          </Button>
        }
      />
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <ProfileSettings settings={data} />
      <GmailAccounts settings={data} />
      <AIModelSettings settings={data} />
      <SecuritySettings settings={data} />
    </div>
  );
}
