from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailSortField(str, Enum):
    RECEIVED_AT = "received_at"
    SUBJECT = "subject"
    SENDER = "sender"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class EmailCategoryLabel(str, Enum):
    IMPORTANT = "important"
    WORK = "work"
    PERSONAL = "personal"
    FINANCE = "finance"
    PROMOTIONS = "promotions"
    SOCIAL = "social"
    UPDATES = "updates"


class EmailListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    gmail_id: str
    sender: str
    sender_name: str | None
    subject: str
    preview: str | None
    received_at: datetime
    is_read: bool
    is_starred: bool
    is_important: bool
    priority_score: int = 0
    is_priority: bool = False
    category: EmailCategoryLabel | None = None
    category_source: str | None = None
    category_confidence: float | None = None
    category_reason: str | None = None
    summary_text: str | None = None


class EmailDetail(EmailListItem):
    thread_id: str | None
    body_text: str | None
    body_html: str | None
    labels: list[str] = Field(default_factory=list)


class EmailListResponse(BaseModel):
    items: list[EmailListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class SyncInboxRequest(BaseModel):
    max_results: int = Field(default=200, ge=1, le=500)
    sync_all: bool = False
    # With sync_all: only run a full re-list when the mailbox isn't mirrored yet or the
    # daily reconcile is due; otherwise do a fast history-based sync.
    auto: bool = False
    incremental: bool = False
    query: str | None = Field(default=None, max_length=500)


class SyncInboxResponse(BaseModel):
    synced_count: int
    new_count: int
    updated_count: int
    account_email: str
    last_synced_at: datetime | None = None
    background: bool = False
    status: str = "completed"


class SyncStatusResponse(BaseModel):
    status: str
    phase: str = "idle"
    # full: blocking first sync; reconcile: quiet daily background re-list.
    mode: str = "full"
    listed_count: int = 0
    fetched_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    error: str | None = None
    last_synced_at: datetime | None = None
    last_full_sync_at: datetime | None = None
    account_email: str | None = None
    # Sync health: messages Gmail reports (excluding spam/trash) vs rows stored locally.
    gmail_total: int | None = None
    stored_count: int | None = None
    # Google revoked/expired the grant; only a new OAuth consent fixes it.
    needs_reconnect: bool = False
    # server: the backend runs full syncs itself; client: the app advances them via /sync/drive.
    driver: str = "server"


class UpdateEmailCategoryRequest(BaseModel):
    category: EmailCategoryLabel
    apply_to_sender: bool = True


class UpdateEmailCategoryResponse(BaseModel):
    email: EmailListItem
    sender_emails_updated: int = 0
