export interface EmailListItem {
  id: string;
  gmail_id: string;
  sender: string;
  sender_name: string | null;
  subject: string;
  preview: string | null;
  received_at: string;
  is_read: boolean;
  is_starred: boolean;
  is_important: boolean;
  /** 0-100 priority computed by the backend; independent of category. */
  priority_score?: number;
  is_priority?: boolean;
  category: string | null;
  /** user | sender_rule | rule | sender_history | thread | ai | gmail */
  category_source?: string | null;
  category_confidence?: number | null;
  category_reason?: string | null;
  summary_text?: string | null;
}

export interface UpdateEmailCategoryResponse {
  email: EmailListItem;
  sender_emails_updated: number;
}

export interface EmailDetail extends EmailListItem {
  thread_id: string | null;
  body_text: string | null;
  body_html: string | null;
  labels: string[];
}

export interface EmailListResponse {
  items: EmailListItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SyncInboxResponse {
  synced_count: number;
  new_count: number;
  updated_count: number;
  account_email: string;
  last_synced_at: string | null;
  background?: boolean;
  status?: string;
}

export interface SyncStatusResponse {
  status: string;
  phase?: string;
  /** "full" = first/explicit sync shown to the user; "reconcile" = quiet daily re-list. */
  mode?: "full" | "reconcile";
  listed_count: number;
  fetched_count: number;
  new_count: number;
  updated_count: number;
  error: string | null;
  last_synced_at: string | null;
  last_full_sync_at?: string | null;
  account_email: string | null;
  /** Messages in Gmail excluding spam/trash, vs rows stored locally. */
  gmail_total?: number | null;
  stored_count?: number | null;
  /** Google revoked or expired the Gmail grant; the user must reconnect. */
  needs_reconnect?: boolean;
  /** "client": the backend is serverless and the open app advances full syncs. */
  driver?: "server" | "client";
}
