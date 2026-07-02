from enum import Enum

from pydantic import BaseModel, Field


class SmartCleanupCategory(str, Enum):
    PRIMARY = "primary"
    PROMOTIONS = "promotions"
    SOCIAL_UPDATES = "social_updates"
    NEWSLETTERS = "newsletters"


SMART_CLEANUP_LABELS: dict[SmartCleanupCategory, str] = {
    SmartCleanupCategory.PRIMARY: "Primary Inbox",
    SmartCleanupCategory.PROMOTIONS: "Promotions",
    SmartCleanupCategory.SOCIAL_UPDATES: "Social & Updates",
    SmartCleanupCategory.NEWSLETTERS: "Newsletters",
}

SMART_CLEANUP_CONFIDENCE: dict[SmartCleanupCategory, str] = {
    SmartCleanupCategory.PRIMARY: "HIGH",
    SmartCleanupCategory.PROMOTIONS: "MEDIUM",
    SmartCleanupCategory.SOCIAL_UPDATES: "MEDIUM",
    SmartCleanupCategory.NEWSLETTERS: "MEDIUM",
}


class CleanupCountItem(BaseModel):
    category: SmartCleanupCategory
    label: str
    count: int
    confidence: str


class CleanupCountsResponse(BaseModel):
    categories: list[CleanupCountItem]


class CleanupAnalyzeRequest(BaseModel):
    category: SmartCleanupCategory
    dry_run: bool = True


class CleanupAnalyzeMessage(BaseModel):
    message_id: str
    confidence: float | None = None
    subject: str | None = None
    reason: str | None = None


class CleanupAnalyzeResponse(BaseModel):
    category: SmartCleanupCategory
    label: str
    total_scanned: int
    kept_count: int
    delete_count: int
    message_ids: list[str]
    samples: list[str] = Field(default_factory=list)
    messages: list[CleanupAnalyzeMessage] = Field(default_factory=list)
    dry_run: bool = True
    job_id: str | None = None
    status: str = "completed"
    progress: float = 1.0


class CleanupAnalyzeProgressResponse(BaseModel):
    job_id: str
    category: SmartCleanupCategory
    status: str
    progress: float
    processed: int
    total: int
    result: CleanupAnalyzeResponse | None = None
    error: str | None = None


class CleanupDeleteRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1)
    permanent: bool = False


class CleanupDeleteResponse(BaseModel):
    deleted: int
    failed: list[str] = Field(default_factory=list)
    trashed: bool = False


class CleanupRestoreRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1)


class CleanupRestoreResponse(BaseModel):
    restored: int
    failed: list[str] = Field(default_factory=list)


class ImportanceTier(str, Enum):
    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    LOW_VALUE = "LOW_VALUE"
    DISPOSABLE = "DISPOSABLE"


class TriageDeleteTier(str, Enum):
    LOW_VALUE = "LOW_VALUE"
    DISPOSABLE = "DISPOSABLE"
    BOTH = "both"


class TriageAnalyzeRequest(BaseModel):
    dry_run: bool = True


class TriageClassificationItem(BaseModel):
    message_id: str
    tier: ImportanceTier
    safe_to_delete: bool
    confidence: float
    reason: str
    subject: str | None = None


class TriageSampleEmails(BaseModel):
    critical: list[str] = Field(default_factory=list)
    important: list[str] = Field(default_factory=list)
    low_value: list[str] = Field(default_factory=list)
    disposable: list[str] = Field(default_factory=list)


class TriageAnalyzeResponse(BaseModel):
    critical: int
    important: int
    low_value: int
    disposable: int
    total_scanned: int
    sample_emails: TriageSampleEmails
    classifications: dict[str, TriageClassificationItem]
    dry_run: bool = True
    job_id: str | None = None
    status: str = "completed"
    progress: float = 1.0


class TriageAnalyzeProgressResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    processed: int
    total: int
    phase: str
    result: TriageAnalyzeResponse | None = None
    error: str | None = None


class TriageDeleteRequest(BaseModel):
    tier: TriageDeleteTier


class TriageDeleteResponse(BaseModel):
    deleted: int
    failed: list[str] = Field(default_factory=list)
    trashed: bool = True
    message_ids: list[str] = Field(default_factory=list)
