import uuid
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base


class OnboardingSession(Base):
    """
    Durable onboarding session for the guided /register flow.
    A partial unique index (uq_onboarding_active_per_user) prevents more than one
    ACTIVE or COMPLETING session per (guild_id, user_id) pair at a time.
    Terminal statuses (COMPLETED, ABANDONED, FAILED) are unconstrained so
    historical records are preserved.
    """
    __tablename__ = "onboarding_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Discord channel where onboarding was initiated
    channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Private or public thread created for this session
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Starter message (used as public thread parent; NULL for private threads)
    starter_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Step machine
    flow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_step: Mapped[str] = mapped_column(String(64), nullable=False)

    # JSONB bag for collected fields (e.g. {"club_name": "ElevenBoss FC"})
    collected_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Lifecycle status: ACTIVE | COMPLETING | COMPLETED | ABANDONED | FAILED
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set when club is successfully created during completion
    club_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )

    # Thread creation mode: PRIVATE | PUBLIC
    thread_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # True once the public-thread visibility warning has been sent
    visibility_warning_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Inactivity nudge timestamp (NULL = not yet nudged)
    nudge_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Lifecycle timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completing_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    abandoned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Sweeper cleanup scheduling
    cleanup_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cleanup_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cleanup_error: Mapped[str | None] = mapped_column(Text, nullable=True)
