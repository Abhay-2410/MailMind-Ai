import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "@/lib/api";
import type { GenerateReplyResponse, ReplyStyle, SummarizeEmailResponse } from "@/types/ai";

export async function summarizeEmail(emailId: string): Promise<SummarizeEmailResponse> {
  return apiRequest<SummarizeEmailResponse>("/ai/summarize", {
    method: "POST",
    body: JSON.stringify({ email_id: emailId }),
  });
}

export async function generateReply(
  emailId: string,
  style: ReplyStyle,
): Promise<GenerateReplyResponse> {
  return apiRequest<GenerateReplyResponse>("/ai/reply", {
    method: "POST",
    body: JSON.stringify({ email_id: emailId, style }),
  });
}

export function useSummarizeEmail(emailId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => summarizeEmail(emailId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useGenerateReply(emailId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (style: ReplyStyle) => generateReply(emailId, style),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
