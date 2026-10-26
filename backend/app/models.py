from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    api_key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    risk_threshold: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    banned_categories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    banned_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risky_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_fields: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    certificate_required_categories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    checks: Mapped[list["ModerationCheck"]] = relationship(back_populates="project", cascade="all, delete")


class ModerationCheck(Base):
    __tablename__ = "moderation_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)

    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_content_id: Mapped[str | None] = mapped_column(String(120), index=True)
    parent_check_id: Mapped[str | None] = mapped_column(ForeignKey("moderation_checks.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    title: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    image_urls: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    decision_source: Mapped[str] = mapped_column(String(30), default="automatic", nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(30), default="approve", nullable=False)
    triggered_rules: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)

    reviewed_by_role: Mapped[str | None] = mapped_column(String(50))
    review_comment: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="checks")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    check_id: Mapped[str | None] = mapped_column(ForeignKey("moderation_checks.id"), index=True)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

