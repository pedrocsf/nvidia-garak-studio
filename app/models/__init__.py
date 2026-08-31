
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TriageStatus(str, enum.Enum):
    new = "new"
    confirmed = "confirmed"
    false_positive = "false_positive"
    accepted_risk = "accepted_risk"


class Role(str, enum.Enum):
    viewer = "viewer"
    operator = "operator"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.admin)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ScanProfile(Base):

    __tablename__ = "scan_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    runs: Mapped[list["Run"]] = relationship(back_populates="profile")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="profile")


class Run(Base):

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("scan_profiles.id"), nullable=True
    )
    garak_run_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    label: Mapped[str] = mapped_column(String(255), default="")
    target_model: Mapped[str] = mapped_column(String(255), default="")
    generator_type: Mapped[str] = mapped_column(String(128), default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.queued, index=True
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    total_hits: Mapped[int] = mapped_column(Integer, default=0)
    attack_surface_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    report_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    hitlog_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    html_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    profile: Mapped[ScanProfile | None] = relationship(back_populates="runs")
    probe_results: Mapped[list["ProbeResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    hits: Mapped[list["Hit"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ProbeResult(Base):

    __tablename__ = "probe_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    probe: Mapped[str] = mapped_column(String(255), index=True)
    detector: Mapped[str] = mapped_column(String(255))
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)

    run: Mapped[Run] = relationship(back_populates="probe_results")


class Hit(Base):

    __tablename__ = "hits"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    probe: Mapped[str] = mapped_column(String(255), index=True)
    detector: Mapped[str] = mapped_column(String(255))
    attempt_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    turns: Mapped[list | None] = mapped_column(JSON, nullable=True)

    triage_status: Mapped[TriageStatus] = mapped_column(
        Enum(TriageStatus), default=TriageStatus.new, index=True
    )
    triage_note: Mapped[str] = mapped_column(Text, default="")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    run: Mapped[Run] = relationship(back_populates="hits")


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        Index("ix_run_events_run_stream_seq", "run_id", "stream", "seq"),
        Index("ix_run_events_run_kind", "run_id", "kind"),
        Index("ix_run_events_run_outcome", "run_id", "outcome"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    stream: Mapped[str] = mapped_column(String(16), default="report")
    seq: Mapped[int] = mapped_column(Integer, default=0)

    kind: Mapped[str] = mapped_column(String(32), default="")
    title: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    ts: Mapped[str | None] = mapped_column(String(64), nullable=True)

    probe: Mapped[str] = mapped_column(String(255), default="", index=True)
    detector: Mapped[str] = mapped_column(String(512), default="")
    outcome: Mapped[str] = mapped_column(String(16), default="info")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempt_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    search_text: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped[Run] = relationship(back_populates="events")


class Secret(Base):

    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("name", name="uq_secret_name"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), index=True)
    env_var: Mapped[str] = mapped_column(String(255), default="")
    ciphertext: Mapped[str] = mapped_column(Text)
    hint: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Schedule(Base):

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    profile_id: Mapped[str] = mapped_column(ForeignKey("scan_profiles.id"))
    name: Mapped[str] = mapped_column(String(255))
    cron: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    profile: Mapped[ScanProfile] = relationship(back_populates="schedules")


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[str] = mapped_column(String(64), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
