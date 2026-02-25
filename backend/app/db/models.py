from datetime import datetime, timezone
from typing import List

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PersonaGroup(Base):
    __tablename__ = "persona_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    personas: Mapped[List["Persona"]] = relationship("Persona", back_populates="group")


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    system_prompt: Mapped[str] = mapped_column(String(4000))
    focus_areas: Mapped[list] = mapped_column(JSON, default=list)
    tone: Mapped[str | None] = mapped_column(String(200), default=None)
    reference_notes: Mapped[str | None] = mapped_column(Text, default=None)
    output_requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    examples: Mapped[list] = mapped_column(JSON, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    color_theme: Mapped[str | None] = mapped_column(String(32), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("persona_groups.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    group: Mapped[PersonaGroup | None] = relationship("PersonaGroup", back_populates="personas")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )
    permissions: Mapped[List["DocumentPermission"]] = relationship(
        "DocumentPermission", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE")
    )
    version_label: Mapped[str] = mapped_column(String(200), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    document: Mapped[Document] = relationship("Document", back_populates="versions")


class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="queued")
    trigger: Mapped[str] = mapped_column(String(50), default="auto")
    provider: Mapped[str] = mapped_column(String(50), default="openai")
    model: Mapped[str] = mapped_column(String(200), default="gpt-4o-mini")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    meta_review_runs: Mapped[List["MetaReviewRun"]] = relationship(
        "MetaReviewRun", back_populates="review_job", cascade="all, delete-orphan"
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    review_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("review_jobs.id", ondelete="SET NULL"), index=True, default=None
    )
    persona_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    excerpt: Mapped[str | None] = mapped_column(String(1000), default=None)
    output_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    meta_comment_sources: Mapped[List["MetaCommentSource"]] = relationship(
        "MetaCommentSource", back_populates="comment", cascade="all, delete-orphan"
    )


class MetaReviewRun(Base):
    __tablename__ = "meta_review_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    review_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("review_jobs.id", ondelete="SET NULL"), index=True, default=None
    )
    input_hash: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    is_synthesized: Mapped[bool] = mapped_column(Boolean, default=True)
    provider: Mapped[str] = mapped_column(String(50), default="openai")
    model: Mapped[str] = mapped_column(String(200), default="gpt-4o-mini")
    error_message: Mapped[str | None] = mapped_column(String(2000), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    review_job: Mapped[ReviewJob | None] = relationship("ReviewJob", back_populates="meta_review_runs")
    comments: Mapped[List["MetaComment"]] = relationship(
        "MetaComment", back_populates="run", cascade="all, delete-orphan"
    )


class MetaComment(Base):
    __tablename__ = "meta_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    meta_review_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meta_review_runs.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), default="clarity")
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    impact: Mapped[str] = mapped_column(String(16), default="medium")
    effort: Mapped[str] = mapped_column(String(16), default="medium")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    why_now: Mapped[str | None] = mapped_column(String(600), default=None)
    recommended_change: Mapped[str | None] = mapped_column(String(1000), default=None)
    verification_step: Mapped[str | None] = mapped_column(String(1000), default=None)
    status: Mapped[str] = mapped_column(String(32), default="open")
    assignee: Mapped[str | None] = mapped_column(String(200), default=None)
    due_at: Mapped[str | None] = mapped_column(String(64), default=None)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    start_offset: Mapped[int] = mapped_column(Integer, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_unsynthesized: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    run: Mapped[MetaReviewRun] = relationship("MetaReviewRun", back_populates="comments")
    sources: Mapped[List["MetaCommentSource"]] = relationship(
        "MetaCommentSource", back_populates="meta_comment", cascade="all, delete-orphan"
    )


class MetaCommentSource(Base):
    __tablename__ = "meta_comment_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    meta_comment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meta_comments.id", ondelete="CASCADE"), index=True
    )
    comment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    reviewer_name: Mapped[str] = mapped_column(String(200))
    reviewer_id: Mapped[int] = mapped_column(Integer)
    original_comment_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    meta_comment: Mapped[MetaComment] = relationship("MetaComment", back_populates="sources")
    comment: Mapped[Comment] = relationship("Comment", back_populates="meta_comment_sources")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(32), default="default")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    account_state: Mapped[str] = mapped_column(String(32), default="active")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    permissions: Mapped[List["DocumentPermission"]] = relationship(
        "DocumentPermission", back_populates="user", cascade="all, delete-orphan"
    )
    auth_accounts: Mapped[List["AuthAccount"]] = relationship(
        "AuthAccount", back_populates="user", cascade="all, delete-orphan"
    )


class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    permission_level: Mapped[str] = mapped_column(String(32), default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    document: Mapped[Document] = relationship("Document", back_populates="permissions")
    user: Mapped[User] = relationship("User", back_populates="permissions")


class AdminActionLog(Base):
    __tablename__ = "admin_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )
    actor_email: Mapped[str | None] = mapped_column(String(320), default=None)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[int | None] = mapped_column(Integer, default=None)
    details: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class AuthAccount(Base):
    __tablename__ = "auth_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="auth_accounts")


class AuthEmailVerification(Base):
    __tablename__ = "auth_email_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class AuthPasswordReset(Base):
    __tablename__ = "auth_password_resets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class AuthMfaChallenge(Base):
    __tablename__ = "auth_mfa_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), index=True)
    code_hash: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class ResourcePolicy(Base):
    __tablename__ = "resource_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    effect: Mapped[str] = mapped_column(String(16), default="deny")
    action: Mapped[str] = mapped_column(String(64), default="document.read", index=True)
    resource_type: Mapped[str] = mapped_column(String(64), default="document", index=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class PolicyDecisionLog(Base):
    __tablename__ = "policy_decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    document_id: Mapped[int | None] = mapped_column(Integer, index=True, default=None)
    action: Mapped[str] = mapped_column(String(64), index=True)
    requested_level: Mapped[str] = mapped_column(String(32), default="viewer")
    base_level: Mapped[str | None] = mapped_column(String(32), default=None)
    final_level: Mapped[str | None] = mapped_column(String(32), default=None)
    outcome: Mapped[str] = mapped_column(String(32), default="denied", index=True)
    matched_policy_ids: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
