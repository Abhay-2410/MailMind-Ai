import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "@/lib/api";
import { resolveInboxView } from "@/lib/inboxViews";
import { useInboxStore } from "@/stores/inboxStore";
import type { EmailCategoryFilter, InboxViewFilter } from "@/stores/inboxStore";
import type {
  EmailDetail,
  EmailListItem,
  EmailListResponse,
  SyncInboxResponse,
  SyncStatusResponse,
  UpdateEmailCategoryResponse,
} from "@/types/email";

export interface InboxQueryParams {
  page?: number;
  page_size?: number;
  is_read?: boolean;
  is_important?: boolean;
  is_priority?: boolean;
  has_summary?: boolean;
  category?: string;
  search?: string;
  sort_by?: "received_at" | "subject" | "sender";
  sort_order?: "asc" | "desc";
}

interface AiSearchResponse {
  natural_query: string;
  gmail_query: string;
  explanation: string;
  model_used: string | null;
  results: EmailListItem[];
  total: number;
}

/** Prefer AI/Gmail search for natural phrases; keep DB substring for short keywords / operators. */
export function looksLikeNaturalLanguageSearch(query: string): boolean {
  const trimmed = query.trim();
  if (trimmed.length < 3) return false;
  // Gmail operators (from:, subject:, is:, newer_than:, etc.)
  if (/^[a-z_]+:\S+/i.test(trimmed) || /\s[a-z_]+:\S+/i.test(trimmed)) return false;
  const words = trimmed.split(/\s+/).filter(Boolean);
  if (words.length >= 3) return true;
  if (
    words.length >= 2 &&
    /\b(from|about|regarding|emails?|messages?|last|week|month|today|yesterday|who|what|when|find|show|unread|important)\b/i.test(
      trimmed,
    )
  ) {
    return true;
  }
  return false;
}

export async function fetchInbox(params: InboxQueryParams = {}): Promise<EmailListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.is_read !== undefined) query.set("is_read", String(params.is_read));
  if (params.is_important !== undefined) query.set("is_important", String(params.is_important));
  if (params.is_priority !== undefined) query.set("is_priority", String(params.is_priority));
  if (params.has_summary !== undefined) query.set("has_summary", String(params.has_summary));
  if (params.category) query.set("category", params.category);
  if (params.search) query.set("search", params.search);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);

  const qs = query.toString();
  return apiRequest<EmailListResponse>(`/inbox${qs ? `?${qs}` : ""}`);
}

async function fetchAiSearchInbox(params: InboxQueryParams): Promise<EmailListResponse> {
  const search = params.search?.trim() ?? "";
  const pageSize = params.page_size ?? 50;
  const response = await apiRequest<AiSearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({
      query: search,
      max_results: Math.min(Math.max(pageSize, 1), 100),
    }),
  });

  let items = response.results;
  if (params.category) {
    items = items.filter((item) => item.category === params.category);
  }
  if (params.is_read !== undefined) {
    items = items.filter((item) => item.is_read === params.is_read);
  }
  if (params.is_important !== undefined) {
    items = items.filter((item) => item.is_important === params.is_important);
  }
  if (params.is_priority !== undefined) {
    items = items.filter((item) => Boolean(item.is_priority) === params.is_priority);
  }
  if (params.has_summary !== undefined) {
    items = items.filter((item) => Boolean(item.summary_text) === params.has_summary);
  }

  return {
    items,
    total: items.length,
    page: 1,
    page_size: pageSize,
    has_more: false,
  };
}

export async function fetchInboxWithSearch(params: InboxQueryParams = {}): Promise<EmailListResponse> {
  const search = params.search?.trim();
  if (search && looksLikeNaturalLanguageSearch(search)) {
    try {
      return await fetchAiSearchInbox(params);
    } catch {
      return fetchInbox(params);
    }
  }
  return fetchInbox(params);
}

export async function fetchEmail(emailId: string): Promise<EmailDetail> {
  return apiRequest<EmailDetail>(`/emails/${emailId}`);
}

export interface SyncInboxOptions {
  maxResults?: number;
  syncAll?: boolean;
  /** With syncAll: let the backend pick a fast history sync when already mirrored. */
  auto?: boolean;
  incremental?: boolean;
  query?: string;
}

export async function fetchSyncStatus(): Promise<SyncStatusResponse> {
  return apiRequest<SyncStatusResponse>("/inbox/sync/status");
}

/** Advances a running full sync by one time-boxed step (serverless backend). */
export async function driveSync(): Promise<SyncStatusResponse> {
  return apiRequest<SyncStatusResponse>("/inbox/sync/drive", { method: "POST" });
}

export async function syncInbox(options: SyncInboxOptions = {}): Promise<SyncInboxResponse> {
  const { maxResults = 100, syncAll = false, auto = false, incremental = false, query } = options;
  return apiRequest<SyncInboxResponse>("/inbox/sync", {
    method: "POST",
    body: JSON.stringify({
      max_results: maxResults,
      sync_all: syncAll,
      auto,
      incremental,
      query: query ?? null,
    }),
  });
}

function buildInboxParams(
  page: number,
  pageSize: number,
  viewFilter: InboxViewFilter,
  category: EmailCategoryFilter,
  search: string,
  view: ReturnType<typeof resolveInboxView>,
): InboxQueryParams {
  const params: InboxQueryParams = { page, page_size: pageSize };

  if (view === "summaries") {
    params.has_summary = true;
  } else {
    if (viewFilter === "unread") params.is_read = false;
    if (viewFilter === "read") params.is_read = true;
    if (viewFilter === "important") params.is_priority = true;
  }

  if (category !== "all") params.category = category;
  if (search.trim()) params.search = search.trim();

  return params;
}

export function useInbox(options?: { enabled?: boolean }) {
  const [searchParams] = useSearchParams();
  const view = resolveInboxView(searchParams.get("view"));
  const { page, pageSize, viewFilter, category, search } = useInboxStore();

  const params = useMemo(
    () => buildInboxParams(page, pageSize, viewFilter, category, search, view),
    [page, pageSize, viewFilter, category, search, view],
  );

  const enabled = options?.enabled ?? true;

  return useQuery({
    queryKey: ["inbox", view, params],
    queryFn: () => fetchInboxWithSearch(params),
    placeholderData: keepPreviousData,
    enabled,
    refetchInterval: 15_000,
  });
}

export function useEmail(emailId: string | undefined) {
  return useQuery({
    queryKey: ["email", emailId],
    queryFn: () => fetchEmail(emailId!),
    enabled: Boolean(emailId),
  });
}

export function useUpdateEmailCategory(emailId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ category, applyToSender }: { category: string; applyToSender: boolean }) =>
      apiRequest<UpdateEmailCategoryResponse>(`/emails/${emailId}/category`, {
        method: "PATCH",
        body: JSON.stringify({ category, apply_to_sender: applyToSender }),
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["email", emailId] }),
        queryClient.invalidateQueries({ queryKey: ["inbox"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });
}
