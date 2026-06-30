import uuid
import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Enum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base

class SchedulerRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    job_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[SchedulerRunStatus] = mapped_column(
        Enum(SchedulerRunStatus, name="scheduler_run_status"), 
        default=SchedulerRunStatus.RUNNING, 
        nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint("job_key", name="uq_scheduler_run_job_key"),
    )
