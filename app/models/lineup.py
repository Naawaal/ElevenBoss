import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Lineup(Base):
    __tablename__ = "lineups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    formation: Mapped[str] = mapped_column(String(20), default="4-4-2", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", back_populates="lineups")
    lineup_players: Mapped[list["LineupPlayer"]] = relationship(
        "LineupPlayer", 
        back_populates="lineup", 
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("formation IN ('4-4-2', '4-3-3', '4-2-3-1', '3-5-2', '5-3-2')", name="chk_lineup_formation"),
        Index("uq_active_lineup", "club_id", unique=True, postgresql_where="is_active = true"),
    )

class LineupPlayer(Base):
    __tablename__ = "lineup_players"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lineup_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lineups.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_starter: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    lineup: Mapped["Lineup"] = relationship("Lineup", back_populates="lineup_players")
    player: Mapped["Player"] = relationship("Player")

    __table_args__ = (
        UniqueConstraint("lineup_id", "player_id", name="uq_lineup_player_link"),
        UniqueConstraint("lineup_id", "slot", name="uq_lineup_player_slot"),
    )
