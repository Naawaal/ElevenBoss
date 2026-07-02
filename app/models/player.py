import uuid
from datetime import datetime
from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    potential: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    wage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fitness: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    sharpness: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    morale: Mapped[int] = mapped_column(Integer, default=75, nullable=False)
    consistency: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    preferred_foot: Mapped[str] = mapped_column(String(10), default="Right", nullable=False)
    weak_foot: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    skill_moves: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    traits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nationality: Mapped[str] = mapped_column(String(64), default="British", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", back_populates="players", foreign_keys=[club_id])

    __table_args__ = (
        CheckConstraint("preferred_foot IN ('Left', 'Right')", name="chk_player_preferred_foot"),
        CheckConstraint("weak_foot BETWEEN 1 AND 5", name="chk_player_weak_foot"),
        CheckConstraint("skill_moves BETWEEN 1 AND 5", name="chk_player_skill_moves"),
        CheckConstraint(
            "position IN ('GK', 'CB', 'LB', 'RB', 'LWB', 'RWB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF')", 
            name="chk_player_position"
        ),
    )
