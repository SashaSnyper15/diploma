from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RuleSet(BaseModel):
    risk_threshold: int = Field(default=50, ge=0, le=100)
    banned_categories: list[str] = Field(default_factory=list)
    banned_keywords: list[str] = Field(default_factory=list)
    risky_keywords: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    certificate_required_categories: list[str] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = ""
    rules: RuleSet = Field(default_factory=RuleSet)


class ProjectUpdateRules(BaseModel):
    rules: RuleSet


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    api_key: str
    is_active: bool
    rules: RuleSet
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModerationRequest(BaseModel):
    project_id: str | None = None
    content_type: Literal["product_card", "announcement"]
    external_content_id: str | None = None
    parent_check_id: str | None = None
    title: str = ""
    description: str = ""
    category: str = ""
    attributes: dict = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list)
    mode: Literal["sync", "async"] = "sync"


class SignalOut(BaseModel):
    code: str
    severity: Literal["low", "medium", "high", "critical"]
    score: int
    message: str


class ModerationResult(BaseModel):
    check_id: str
    project_id: str
    status: str
    recommended_action: str
    risk_score: int
    signals: list[SignalOut]
    version: int
    parent_check_id: str | None
    created_at: datetime


class CheckOut(BaseModel):
    id: str
    project_id: str
    content_type: str
    external_content_id: str | None
    parent_check_id: str | None
    version: int
    title: str
    description: str
    category: str
    attributes: dict
    image_urls: list[str]
    status: str
    decision_source: str
    risk_score: int
    recommended_action: str
    triggered_rules: list[SignalOut]
    reviewed_by_role: str | None
    review_comment: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CheckDetail(CheckOut):
    related_versions: list["CheckOut"] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    action: Literal["approve", "reject", "escalate"]
    comment: str = ""


class AnalyticsOut(BaseModel):
    total_checks: int
    by_status: dict[str, int]
    top_risk_signals: list[dict]


CheckDetail.model_rebuild()
