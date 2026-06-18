import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api";
import type { AssistantResponse } from "@/types/ai";

export async function askAssistant(question: string): Promise<AssistantResponse> {
  return apiRequest<AssistantResponse>("/ai/assistant", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function useAskAssistant() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: askAssistant,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
