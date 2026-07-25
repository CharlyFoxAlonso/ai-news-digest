from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class RunStatus(StrEnum):
    NOT_STARTED = "not_started"
    STARTED = "started"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERY_UNCERTAIN = "delivery_uncertain"


class RunKind(StrEnum):
    PRINCIPAL = "principal"
    RECOVERY = "recovery"
    MANUAL = "manual"


class Article(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    article_id: str
    source_name: str
    source_priority: int = Field(ge=0, le=100)
    is_official_source: bool
    title: str
    url_original: HttpUrl
    url_canonical: HttpUrl
    published_at_utc: datetime
    description: str = ""
    category: str = "other"
    heuristic_score: float = 0
    llm_score: float | None = Field(default=None, ge=0, le=100)
    llm_confidence: float | None = Field(default=None, ge=0, le=1)
    ranking_reason: str = ""

    @field_validator("published_at_utc")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at_utc must be timezone-aware")
        return value


class DigestEntry(BaseModel):
    article: Article
    summary_es: str = Field(max_length=320)
    why_it_matters: str
    used_fallback: bool = False


class DailyRunState(BaseModel):
    schema_version: int = 1
    digest_date_local: str
    status: RunStatus = RunStatus.NOT_STARTED
    run_kind: RunKind
    run_id: str
    started_at_utc: datetime | None = None
    finished_at_utc: datetime | None = None
    smtp_message_id: str | None = None
    selected_articles: list[str] = Field(default_factory=list)
    last_error: str | None = None


class HistoryEntry(BaseModel):
    digest_date_local: str
    canonical_urls: list[str]
    article_hashes: list[str]
    titles: list[str]
    smtp_accepted_at_utc: datetime
