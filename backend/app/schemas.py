from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config import DEFAULT_DOMAIN_DENYLIST

ChosenSource = Literal["ct_registry", "domain_rdap", "whoisxml", "social_hint", "not_found"]


class JobSettings(BaseModel):
    high_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    prefer_earliest_known_date: bool = False
    enable_rdap_lookup: bool = True
    enable_whois_fallback: bool = True
    enable_social_hints: bool = False
    min_plausible_date: str = "1900-01-01"
    denylist_domains: list[str] = Field(default_factory=lambda: list(DEFAULT_DOMAIN_DENYLIST))

    @field_validator("denylist_domains")
    @classmethod
    def normalize_denylist(cls, values: list[str]) -> list[str]:
        return sorted({v.strip().lower() for v in values if v and v.strip()})


class JobCreateResponse(BaseModel):
    job_id: str


class JobCounts(BaseModel):
    total_rows: int = 0
    auto_matched: int = 0
    needs_review: int = 0
    not_found: int = 0
    filled_via_domain: int = 0
    filled_via_social: int = 0


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress_done: int = 0
    progress_total: int = 0
    progress_pct: float = 0.0
    message: str = ""
    counts: JobCounts = Field(default_factory=JobCounts)
    can_download: bool = False
    error: str | None = None


class ReviewCandidate(BaseModel):
    name: str = ""
    city: str = ""
    zip: str = ""
    entity_id: str = ""
    registration_date_raw: str = ""
    similarity: float = 0.0
    confidence: float = 0.0


class ReviewRow(BaseModel):
    row_index: int
    business: str = ""
    city: str = ""
    zip: str = ""
    url: str = ""
    candidates: list[ReviewCandidate] = Field(default_factory=list)


class ReviewResponse(BaseModel):
    job_id: str
    rows: list[ReviewRow] = Field(default_factory=list)


class ReviewSelection(BaseModel):
    row_index: int
    candidate_index: int | None = None
    no_match: bool = False


class ReviewSubmitRequest(BaseModel):
    selections: list[ReviewSelection] = Field(default_factory=list)


class CacheClearResponse(BaseModel):
    cleared: bool


class AppConfigResponse(BaseModel):
    defaults: JobSettings
    whois_key_present: bool
    feature_social_hints_env: bool

