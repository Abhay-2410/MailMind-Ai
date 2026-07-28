import { createContext, useContext, type ReactNode } from "react";

import { useAutoSync } from "@/hooks/useAutoSync";

type SyncContextValue = ReturnType<typeof useAutoSync>;

const SyncContext = createContext<SyncContextValue | null>(null);

export function SyncProvider({ children }: { children: ReactNode }) {
  const value = useAutoSync();
  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

export function useSyncStatus(): SyncContextValue {
  const ctx = useContext(SyncContext);
  if (!ctx) {
    throw new Error("useSyncStatus must be used within SyncProvider");
  }
  return ctx;
}
