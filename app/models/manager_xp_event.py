import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class ManagerXPEvent(Base):
    __tablename__ = "manager_xp_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("managers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)

    xp_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship to Manager
    manager: Mapped["Manager"] = relationship("Manager", foreign_keys=[manager_id])

    __table_args__ = (
        UniqueConstraint(
            "manager_id",
            "guild_id",
            "source_type",
            "source_id",
            name="uq_manager_xp_event_source",
        ),
    )
