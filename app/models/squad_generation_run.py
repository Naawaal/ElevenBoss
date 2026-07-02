import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base


class SquadGenerationRun(Base):
    """
    Idempotency guard for PlayerService.create_squad().
    One row per club — unique on both club_id and generation_key.
    Checked before generation begins; marked COMPLETED on success.
    """
    __tablename__ = "squad_generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # Deterministic key encoding the source of this generation run
    # e.g. "onboarding:<session_id>" or "initial:<club_id>"
    generation_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    # PENDING | IN_PROGRESS | COMPLETED | FAILED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
