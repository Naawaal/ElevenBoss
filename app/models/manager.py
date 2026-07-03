import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Manager(Base):
    __tablename__ = "managers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    discord_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True)
    career_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    def __init__(self, **kwargs):
        if "career_xp" not in kwargs:
            kwargs["career_xp"] = 0
        if "coins" not in kwargs:
            kwargs["coins"] = 1000
        super().__init__(**kwargs)

    # Relationships
    club: Mapped["Club"] = relationship(
        "Club",
        back_populates="manager",
        uselist=False,
        foreign_keys="Club.manager_id"
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "discord_user_id", name="uq_manager_guild_user"),
    )
