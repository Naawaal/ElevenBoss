import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class FriendlyThreadBreadcrumb(Base):
    """
    Breadcrumb table to persist progressive friendly match thread lifecycle metadata
    for crash-recovery and sweeper-based cleanup. Zero football data is stored.
    """
    __tablename__ = "friendly_thread_breadcrumbs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    parent_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    participant_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # PLAYING, COMPLETED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cleanup_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleanup_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleanup_error: Mapped[str | None] = mapped_column(Text, nullable=True)

class FriendlyCooldown(Base):
    """
    Persisted cooldowns for friendly match challenges to prevent spam rate-limit resetting on restarts.
    """
    __tablename__ = "friendly_cooldowns"

    guild_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    challenger_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    opponent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
