export type SmartCleanupCategoryId = "primary" | "promotions" | "social_updates" | "newsletters";

export type SmartCleanupConfidence = "HIGH" | "MEDIUM";

export type SmartCleanupRowState =
  | "idle"
  | "analyzing"
  | "results_ready"
  | "deleting"
  | "done";

export interface CleanupCountItem {
  category: SmartCleanupCategoryId;
  label: string;
  count: number;
  confidence: SmartCleanupConfidence;
}

export interface CleanupCountsResponse {
  categories: CleanupCountItem[];
}

export interface CleanupAnalyzeResponse {
  category: SmartCleanupCategoryId;
  label: string;
  total_scanned: number;
  kept_count: number;
  delete_count: number;
  message_ids: string[];
  samples: string[];
  dry_run: boolean;
  job_id: string | null;
  status: string;
  progress: number;
}

export interface CleanupAnalyzeProgressResponse {
  job_id: string;
  category: SmartCleanupCategoryId;
  status: string;
  progress: number;
  processed: number;
  total: number;
  result: CleanupAnalyzeResponse | null;
  error: string | null;
}

export interface CleanupDeleteResponse {
  deleted: number;
  failed: string[];
  trashed: boolean;
}

export interface CleanupRestoreResponse {
  restored: number;
  failed: string[];
}

export interface SmartCleanupRowData {
  state: SmartCleanupRowState;
  count: number;
  analyzeProgress: number;
  deleteProgress: number;
  deletedCount: number;
  totalToDelete: number;
  messageIds: string[];
  samples: string[];
  keptCount: number;
  error: string | null;
  summary: string | null;
  undoDeadline: number | null;
}

export interface SmartCleanupCategoryConfig {
  id: SmartCleanupCategoryId;
  label: string;
  confidence: SmartCleanupConfidence;
}

export type ImportanceTier = "CRITICAL" | "IMPORTANT" | "LOW_VALUE" | "DISPOSABLE";

export type TriageDeleteTier = "LOW_VALUE" | "DISPOSABLE" | "both";

export interface TriageClassificationItem {
  message_id: string;
  tier: ImportanceTier;
  safe_to_delete: boolean;
  confidence: number;
  reason: string;
  subject: string | null;
}

export interface TriageSampleEmails {
  critical: string[];
  important: string[];
  low_value: string[];
  disposable: string[];
}

export interface TriageAnalyzeResponse {
  critical: number;
  important: number;
  low_value: number;
  disposable: number;
  total_scanned: number;
  sample_emails: TriageSampleEmails;
  classifications: Record<string, TriageClassificationItem>;
  dry_run: boolean;
  job_id: string | null;
  status: string;
  progress: number;
}

export interface TriageAnalyzeProgressResponse {
  job_id: string;
  status: string;
  progress: number;
  processed: number;
  total: number;
  phase: string;
  result: TriageAnalyzeResponse | null;
  error: string | null;
}

export interface TriageDeleteResponse {
  deleted: number;
  failed: string[];
  trashed: boolean;
  message_ids: string[];
}

export type InboxTriageState = "idle" | "analyzing" | "complete" | "deleting";

export interface InboxTriageData {
  state: InboxTriageState;
  processed: number;
  total: number;
  progress: number;
  phase: string | null;
  summary: TriageAnalyzeResponse | null;
  error: string | null;
  undoDeadline: number | null;
  deletedMessageIds: string[];
  confirmTier: TriageDeleteTier | null;
}
