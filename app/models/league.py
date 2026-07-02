import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Enum, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class LeagueStatus(str, enum.Enum):
    DRAFT = "draft"
    STARTING = "starting"
    ACTIVE = "active"
    COMPLETED = "completed"
    NEEDS_ADMIN_REVIEW = "needs_admin_review"
    CANCELLED = "cancelled"

class League(Base):
    __tablename__ = "leagues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_clubs: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    status: Mapped[LeagueStatus] = mapped_column(
        Enum(LeagueStatus, name="league_status", values_callable=lambda obj: [item.value for item in obj]), 
        default=LeagueStatus.DRAFT, 
        nullable=False
    )
    
    # Registration & LifeCycle Orchestrator configuration
    registration_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_deadline_timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    auto_start_after_deadline: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fill_bots_after_deadline: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minimum_human_clubs: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    target_club_count: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    review_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

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
