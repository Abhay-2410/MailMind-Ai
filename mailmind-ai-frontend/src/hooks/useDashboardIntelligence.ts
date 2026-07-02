import { useMemo } from "react";

import { mapDashboardIntelligence } from "@/lib/dashboard/intelligenceMappers";
import type { DashboardResponse } from "@/types/dashboard";

export function useDashboardIntelligence(data: DashboardResponse | undefined) {
  return useMemo(() => {
    if (!data) return null;
    return mapDashboardIntelligence(data);
  }, [data]);
}
