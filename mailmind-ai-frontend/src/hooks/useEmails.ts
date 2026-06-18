import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { apiRequest } from "@/lib/api";
import { useInboxStore } from "@/stores/inboxStore";
import type { EmailCategoryFilter, InboxViewFilter } from "@/stores/inboxStore";
import type { EmailDetail, EmailListResponse, SyncInboxResponse } from "@/types/email";

export interface InboxQueryParams {
  page?: number;
  page_size?: number;
  is_read?: boolean;
  is_important?: boolean;
  category?: string;
  search?: string;
  sort_by?: "received_at" | "subject" | "sender";
  sort_order?: "asc" | "desc";
}

export async function fetchInbox(params: InboxQueryParams = {}): Promise<EmailListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.is_read !== undefined) query.set("is_read", String(params.is_read));
  if (params.is_important !== undefined) query.set("is_important", String(params.is_important));
  if (params.category) query.set("category", params.category);
  if (params.search) query.set("search", params.search);
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_order) query.set("sort_order", params.sort_order);

  const qs = query.toString();
  return apiRequest<EmailListResponse>(`/inbox${qs ? `?${qs}` : ""}`);
}

export async function fetchEmail(emailId: string): Promise<EmailDetail> {
  return apiRequest<EmailDetail>(`/emails/${emailId}`);
}

export interface SyncInboxOptions {
  maxResults?: number;
  syncAll?: boolean;
  query?: string;
}

export async function syncInbox(options: SyncInboxOptions = {}): Promise<SyncInboxResponse> {
  const { maxResults = 50, syncAll = false, query } = options;
  return apiRequest<SyncInboxResponse>("/inbox/sync", {
    method: "POST",
    body: JSON.stringify({
      max_results: maxResults,
      sync_all: syncAll,
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
): InboxQueryParams {
  const params: InboxQueryParams = { page, page_size: pageSize };

  if (viewFilter === "unread") params.is_read = false;
  if (viewFilter === "read") params.is_read = true;
  if (viewFilter === "important") params.is_important = true;
  if (category !== "all") params.category = category;
  if (search.trim()) params.search = search.trim();

  return params;
}

export function useInbox() {
  const { page, pageSize, viewFilter, category, search } = useInboxStore();

  const params = useMemo(
    () => buildInboxParams(page, pageSize, viewFilter, category, search),
    [page, pageSize, viewFilter, category, search],
  );

  return useQuery({
    queryKey: ["inbox", params],
    queryFn: () => fetchInbox(params),
    placeholderData: keepPreviousData,
  });
}

export function useEmail(emailId: string | undefined) {
  return useQuery({
    queryKey: ["email", emailId],
    queryFn: () => fetchEmail(emailId!),
    enabled: Boolean(emailId),
  });
}
