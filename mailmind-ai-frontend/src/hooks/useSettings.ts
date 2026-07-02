import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api";
import { applyTheme } from "@/lib/theme";
import type { AIModelOption } from "@/types/settings";
import type { SettingsResponse, UpdateSettingsPayload } from "@/types/settings";

export async function fetchSettings(): Promise<SettingsResponse> {
  return apiRequest<SettingsResponse>("/settings");
}

export async function updateSettings(payload: UpdateSettingsPayload): Promise<SettingsResponse> {
  return apiRequest<SettingsResponse>("/settings", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchAIModels(): Promise<AIModelOption[]> {
  return apiRequest<AIModelOption[]>("/ai/models");
}

export function useSettings(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: options?.enabled ?? true,
  });
}

export function useAIModels() {
  return useQuery({
    queryKey: ["ai-models"],
    queryFn: fetchAIModels,
    staleTime: 1000 * 60 * 10,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["settings"], data);
      if (data.theme) {
        applyTheme(data.theme);
      }
    },
  });
}
