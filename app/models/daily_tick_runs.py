# app/models/daily_tick_runs.py
import uuid
import enum
from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, Enum, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base

class DailyTickRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class DailyTickRun(Base):
    __tablename__ = "daily_tick_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tick_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DailyTickRunStatus] = mapped_column(
        Enum(DailyTickRunStatus, name="daily_tick_run_status", values_callable=lambda obj: [item.value for item in obj]),
        default=DailyTickRunStatus.RUNNING,
        nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("guild_id", "tick_date", name="uq_daily_tick_run_guild_date"),
    )
