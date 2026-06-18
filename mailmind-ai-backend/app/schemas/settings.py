from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ThemePreference(str, Enum):
    LIGHT = "light"
    SYSTEM = "system"


class AccountSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str | None
    is_primary: bool
    is_active: bool
    last_synced_at: datetime | None


class SettingsResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    display_name: str | None
    timezone: str
    ai_provider: str
    ai_model: str
    theme: ThemePreference
    google_connected: bool
    accounts: list[AccountSummary]


class UpdateSettingsRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    ai_provider: str | None = Field(default=None, max_length=50)
    ai_model: str | None = Field(default=None, max_length=100)
    theme: ThemePreference | None = None
