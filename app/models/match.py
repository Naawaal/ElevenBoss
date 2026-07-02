import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class MatchEventType(str, enum.Enum):
    GOAL = "goal"
    ASSIST = "assist"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    INJURY = "injury"
    SUBSTITUTION = "substitution"
    VAR = "var"
    PENALTY = "penalty"
    OWN_GOAL = "own_goal"
    MATCH_START = "match_start"
    HALF_TIME = "half_time"
    FULL_TIME = "full_time"

class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fixture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )
    home_club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    away_club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    home_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    away_goals: Mapped[int] = mapped_column(Integer, nullable=False)
    home_possession: Mapped[int] = mapped_column(Integer, nullable=False)  # Percentage (e.g. 52)
    away_possession: Mapped[int] = mapped_column(Integer, nullable=False)  # Percentage (e.g. 48)
    home_shots: Mapped[int] = mapped_column(Integer, nullable=False)
    away_shots: Mapped[int] = mapped_column(Integer, nullable=False)
    home_shots_on_target: Mapped[int] = mapped_column(Integer, nullable=False)
    away_shots_on_target: Mapped[int] = mapped_column(Integer, nullable=False)
    motm_player_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    # Relationships
    fixture: Mapped["Fixture"] = relationship("Fixture", back_populates="match_result", foreign_keys=[fixture_id])
    home_club: Mapped["Club"] = relationship("Club", foreign_keys=[home_club_id])
    away_club: Mapped["Club"] = relationship("Club", foreign_keys=[away_club_id])
    motm_player: Mapped["Player"] = relationship("Player", foreign_keys=[motm_player_id])

class MatchEvent(Base):
    __tablename__ = "match_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fixture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False, index=True)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[MatchEventType] = mapped_column(Enum(MatchEventType, name="match_event_type", values_callable=lambda obj: [item.value for item in obj]), nullable=False)
    club_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True)
    player_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=True)
    secondary_player_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    fixture: Mapped["Fixture"] = relationship("Fixture", back_populates="match_events", foreign_keys=[fixture_id])
    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id])
    player: Mapped["Player"] = relationship("Player", foreign_keys=[player_id])
    secondary_player: Mapped["Player"] = relationship("Player", foreign_keys=[secondary_player_id])
