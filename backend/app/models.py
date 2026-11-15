from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(80))
    role_label: Mapped[str] = mapped_column(String(80), default="团队成员")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[Member] = relationship()


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("project_id", "member_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    role: Mapped[str] = mapped_column(String(30), default="member")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    member: Mapped[Member] = relationship()


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("project_id", "display_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    display_no: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[str] = mapped_column(Text)
    progress: Mapped[str] = mapped_column(String(30), default="not_started")
    review_state: Mapped[str] = mapped_column(String(30), default="draft")
    owner_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    event_sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped[Member] = relationship()


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (UniqueConstraint("task_id", "display_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    display_no: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    source_note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    versions: Mapped[list[MaterialVersion]] = relationship(
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="MaterialVersion.version_no",
    )


class MaterialVersion(Base):
    __tablename__ = "material_versions"
    __table_args__ = (UniqueConstraint("material_id", "version_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    material: Mapped[Material] = relationship(back_populates="versions")


class GenerationPreview(Base):
    __tablename__ = "generation_previews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    material_version_ids: Mapped[list[str]] = mapped_column(JSON)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    character_count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    preview_id: Mapped[str] = mapped_column(
        ForeignKey("generation_previews.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(30), default="pending")
    mode: Mapped[str] = mapped_column(String(20), default="normal")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HandoffDraft(Base):
    __tablename__ = "handoff_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    origin: Mapped[str] = mapped_column(String(30))
    sections: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    generation_run_id: Mapped[str | None] = mapped_column(ForeignKey("generation_runs.id"))
    edited_by: Mapped[str] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    citations: Mapped[list[DraftCitation]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )


class DraftCitation(Base):
    __tablename__ = "draft_citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("handoff_drafts.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(30))
    material_version_id: Mapped[str] = mapped_column(ForeignKey("material_versions.id"))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)

    draft: Mapped[HandoffDraft] = relationship(back_populates="citations")


class ConfirmedHandoff(Base):
    __tablename__ = "confirmed_handoffs"
    __table_args__ = (UniqueConstraint("task_id", "version_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    task_snapshot: Mapped[dict] = mapped_column(JSON)
    sections: Mapped[dict] = mapped_column(JSON)
    confirmed_by: Mapped[str] = mapped_column(ForeignKey("members.id"))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    citations: Mapped[list[ConfirmedCitation]] = relationship(
        back_populates="handoff", cascade="all, delete-orphan"
    )


class ConfirmedCitation(Base):
    __tablename__ = "confirmed_citations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    handoff_id: Mapped[str] = mapped_column(ForeignKey("confirmed_handoffs.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(30))
    material_version_id: Mapped[str] = mapped_column(ForeignKey("material_versions.id"))
    source_material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    source_content_hash: Mapped[str] = mapped_column(String(64))
    quote_hash: Mapped[str] = mapped_column(String(64))
    hash_algorithm: Mapped[str] = mapped_column(String(20), default="sha256-v1")

    handoff: Mapped[ConfirmedHandoff] = relationship(back_populates="citations")


class HandoffRequest(Base):
    __tablename__ = "handoff_requests"
    __table_args__ = (
        Index(
            "uq_handoff_requests_pending_task",
            "task_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    confirmed_handoff_id: Mapped[str] = mapped_column(ForeignKey("confirmed_handoffs.id"))
    sender_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    recipient_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class HandoffReceipt(Base):
    __tablename__ = "handoff_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("handoff_requests.id", ondelete="CASCADE"), unique=True
    )
    recipient_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        UniqueConstraint("event_ref"),
        UniqueConstraint("task_id", "seq"),
        Index("ix_task_events_task_created", "task_id", "created_at"),
        Index("ix_task_events_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_ref: Mapped[str] = mapped_column(String(50))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("members.id"))
    event_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="succeeded")
    lifecycle: Mapped[str] = mapped_column(String(30), default="active")
    subject_key: Mapped[str | None] = mapped_column(String(160))
    parent_event_id: Mapped[str | None] = mapped_column(ForeignKey("task_events.id"))
    correlation_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(30), default="user")
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
