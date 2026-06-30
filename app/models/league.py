import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class LeagueStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class League(Base):
    __tablename__ = "leagues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_clubs: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    status: Mapped[LeagueStatus] = mapped_column(
        Enum(LeagueStatus, name="league_status"), 
        default=LeagueStatus.DRAFT, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    seasons: Mapped[list["Season"]] = relationship(
        "Season", 
        back_populates="league", 
        cascade="all, delete-orphan"
    )
    clubs: Mapped[list["Club"]] = relationship(
        "Club", 
        back_populates="league",
        foreign_keys="Club.league_id"
    )

    __table_args__ = (
        UniqueConstraint("guild_id", "name", name="uq_league_guild_name"),
    )
