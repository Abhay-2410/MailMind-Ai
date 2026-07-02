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
  category: string | null;
  summary_text?: string | null;
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
  listed_count: number;
  fetched_count: number;
  new_count: number;
  updated_count: number;
  error: string | null;
  last_synced_at: string | null;
  account_email: string | null;
}
