from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.email import EmailListItem


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    max_results: int = Field(default=50, ge=1, le=100)


class SearchResponse(BaseModel):
    natural_query: str
    gmail_query: str
    explanation: str
    model_used: str | None = None
    results: list[EmailListItem]
    total: int


class SearchHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    natural_query: str
    gmail_query: str
    results_count: int
    model_used: str | None
    created_at: datetime
