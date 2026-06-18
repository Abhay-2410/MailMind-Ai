import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api";
import type { DashboardResponse } from "@/types/dashboard";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiRequest<DashboardResponse>("/dashboard"),
  });
}
