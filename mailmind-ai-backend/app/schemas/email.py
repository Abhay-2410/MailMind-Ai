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
    category: EmailCategoryLabel | None = None


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
    max_results: int = Field(default=50, ge=1, le=500)
    sync_all: bool = False
    query: str | None = Field(default=None, max_length=500)


class SyncInboxResponse(BaseModel):
    synced_count: int
    new_count: int
    updated_count: int
    account_email: str
    last_synced_at: datetime
