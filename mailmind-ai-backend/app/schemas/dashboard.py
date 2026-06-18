from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ActivityType(str, Enum):
    EMAIL_RECEIVED = "email_received"
    AI_SUMMARIZE = "ai_summarize"
    AI_REPLY = "ai_reply"
    AI_CATEGORIZE = "ai_categorize"
    AI_SEARCH = "ai_search"
    AI_ASSISTANT = "ai_assistant"
    INBOX_SYNC = "inbox_sync"


class CategoryStat(BaseModel):
    category: str
    label: str
    count: int
    percentage: float


class ActivityItem(BaseModel):
    id: UUID
    type: ActivityType
    title: str
    description: str
    timestamp: datetime


class DashboardStats(BaseModel):
    total_emails: int
    unread_emails: int
    important_emails: int
    ai_actions_saved: int
    categorized_emails: int
    last_synced_at: datetime | None = None


class DashboardResponse(BaseModel):
    stats: DashboardStats
    categories: list[CategoryStat]
    recent_activity: list[ActivityItem] = Field(default_factory=list)
