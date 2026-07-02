import { ApiError, apiRequest } from "@/lib/api";
import type {
  CleanupAnalyzeProgressResponse,
  CleanupAnalyzeResponse,
  CleanupCountsResponse,
  CleanupDeleteResponse,
  CleanupRestoreResponse,
  SmartCleanupCategoryId,
  TriageAnalyzeProgressResponse,
  TriageAnalyzeResponse,
  TriageDeleteResponse,
  TriageDeleteTier,
} from "@/types/cleanup";

const DELETE_TIMEOUT_MS = 30 * 60 * 1000;
const POLL_INTERVAL_MS = 800;

export function mapSmartCleanupError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Rate limited — wait 30s and retry";
    return error.message;
  }
  if (error instanceof Error) {
    if (error.name === "AbortError") return "Operation timed out — try again";
    return error.message;
  }
  return "Something went wrong";
}

export async function fetchSmartCleanupCounts(): Promise<CleanupCountsResponse> {
  return apiRequest<CleanupCountsResponse>("/cleanup/counts");
}

export async function startCleanupAnalyze(
  category: SmartCleanupCategoryId,
  dryRun = true,
): Promise<CleanupAnalyzeProgressResponse> {
  return apiRequest<CleanupAnalyzeProgressResponse>("/cleanup/analyze", {
    method: "POST",
    body: JSON.stringify({ category, dry_run: dryRun }),
  });
}

export async function fetchCleanupAnalyzeProgress(
  jobId: string,
): Promise<CleanupAnalyzeProgressResponse> {
  return apiRequest<CleanupAnalyzeProgressResponse>(`/cleanup/analyze/${jobId}`);
}

export async function pollCleanupAnalyze(
  jobId: string,
  onProgress?: (progress: CleanupAnalyzeProgressResponse) => void,
): Promise<CleanupAnalyzeResponse> {
  while (true) {
    const status = await fetchCleanupAnalyzeProgress(jobId);
    onProgress?.(status);

    if (status.status === "completed" && status.result) {
      return status.result;
    }
    if (status.status === "failed") {
      throw new Error(status.error ?? "Analysis failed");
    }

    await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

export async function deleteCleanupMessages(
  messageIds: string[],
  permanent = false,
): Promise<CleanupDeleteResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), DELETE_TIMEOUT_MS);

  try {
    return await apiRequest<CleanupDeleteResponse>("/cleanup/delete", {
      method: "POST",
      body: JSON.stringify({ message_ids: messageIds, permanent }),
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function restoreCleanupMessages(
  messageIds: string[],
): Promise<CleanupRestoreResponse> {
  return apiRequest<CleanupRestoreResponse>("/cleanup/restore", {
    method: "POST",
    body: JSON.stringify({ message_ids: messageIds }),
  });
}

export async function deleteCleanupMessagesInChunks(
  messageIds: string[],
  permanent: boolean,
  onChunk: (deleted: number, total: number) => void,
  chunkSize = 100,
): Promise<CleanupDeleteResponse> {
  let deleted = 0;
  const failed: string[] = [];

  for (let i = 0; i < messageIds.length; i += chunkSize) {
    const chunk = messageIds.slice(i, i + chunkSize);
    const result = await deleteCleanupMessages(chunk, permanent);
    deleted += result.deleted;
    failed.push(...result.failed);
    onChunk(deleted, messageIds.length);
  }

  return { deleted, failed, trashed: !permanent };
}

export async function startTriageAnalyze(
  dryRun = true,
): Promise<TriageAnalyzeProgressResponse> {
  return apiRequest<TriageAnalyzeProgressResponse>("/cleanup/triage/analyze", {
    method: "POST",
    body: JSON.stringify({ dry_run: dryRun }),
  });
}

export async function fetchTriageAnalyzeProgress(
  jobId: string,
): Promise<TriageAnalyzeProgressResponse> {
  return apiRequest<TriageAnalyzeProgressResponse>(`/cleanup/triage/analyze/${jobId}`);
}

export async function pollTriageAnalyze(
  jobId: string,
  onProgress?: (progress: TriageAnalyzeProgressResponse) => void,
): Promise<TriageAnalyzeResponse> {
  while (true) {
    const status = await fetchTriageAnalyzeProgress(jobId);
    onProgress?.(status);

    if (status.status === "completed" && status.result) {
      return status.result;
    }
    if (status.status === "failed") {
      throw new Error(status.error ?? "Inbox triage analysis failed");
    }

    await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

export async function deleteTriageTier(
  tier: TriageDeleteTier,
): Promise<TriageDeleteResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), DELETE_TIMEOUT_MS);

  try {
    return await apiRequest<TriageDeleteResponse>("/cleanup/triage/delete", {
      method: "POST",
      body: JSON.stringify({ tier }),
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}
