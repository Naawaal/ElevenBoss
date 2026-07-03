import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class FixtureStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LOCKED = "locked"
    SIMULATING = "simulating"
    PLAYED = "played"
    VOID = "void"

class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    home_club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    away_club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[FixtureStatus] = mapped_column(
        Enum(FixtureStatus, name="fixture_status", values_callable=lambda obj: [item.value for item in obj]), 
        default=FixtureStatus.SCHEDULED, 
        nullable=False,
        index=True
    )
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    simulation_seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consequences_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    season: Mapped["Season"] = relationship("Season", back_populates="fixtures")
    home_club: Mapped["Club"] = relationship("Club", foreign_keys=[home_club_id], back_populates="home_fixtures")
    away_club: Mapped["Club"] = relationship("Club", foreign_keys=[away_club_id], back_populates="away_fixtures")
    
    # We use string names for match results/events to avoid circular imports
    match_result: Mapped["MatchResult"] = relationship(
        "MatchResult", 
        back_populates="fixture", 
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="MatchResult.fixture_id"
    )
    match_events: Mapped[list["MatchEvent"]] = relationship(
        "MatchEvent", 
        back_populates="fixture", 
        cascade="all, delete-orphan",
        foreign_keys="MatchEvent.fixture_id"
    )

    __table_args__ = (
        UniqueConstraint("season_id", "week", "home_club_id", "away_club_id", name="uq_fixture_week_clubs"),
    )
