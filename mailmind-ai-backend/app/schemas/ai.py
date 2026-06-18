import json
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ReplyStyle(str, Enum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    FORMAL = "formal"
    SHORT = "short"


class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class EmailCategoryLabel(str, Enum):
    IMPORTANT = "important"
    WORK = "work"
    PERSONAL = "personal"
    FINANCE = "finance"
    PROMOTIONS = "promotions"
    SOCIAL = "social"
    UPDATES = "updates"


class AIModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    description: str
    is_default: bool


class SummarizeEmailRequest(BaseModel):
    email_id: UUID


class SummarizeEmailResponse(BaseModel):
    email_id: UUID
    summary_text: str
    key_points: list[str]
    action_items: list[str]
    important_dates: list[str]
    priority_level: PriorityLevel
    model_used: str


class GenerateReplyRequest(BaseModel):
    email_id: UUID
    style: ReplyStyle = ReplyStyle.PROFESSIONAL


class GenerateReplyResponse(BaseModel):
    email_id: UUID
    reply: str
    style: ReplyStyle
    model_used: str


class CategorizeEmailRequest(BaseModel):
    email_id: UUID


class CategorizeEmailResponse(BaseModel):
    email_id: UUID
    category: EmailCategoryLabel
    confidence: float
    model_used: str


class TranslateSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)


class TranslateSearchResponse(BaseModel):
    natural_query: str
    gmail_query: str
    explanation: str
    model_used: str


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class AssistantResponse(BaseModel):
    answer: str
    model_used: str
