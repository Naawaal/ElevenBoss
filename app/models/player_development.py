# app/models/player_development.py

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String, Integer, Boolean, DateTime, ForeignKey,
    CheckConstraint, Numeric, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base


class PlayerDevelopmentState(Base):
    """
    One row per player per season. Accumulates training XP, match XP, and
    readiness modifier. Tracks the season-end OVR bonus lifecycle.

    Only created for human-club players. Bot clubs are excluded at every
    write boundary in the training service.

    Ownership:
    - training_xp, match_xp, weeks_trained, readiness_modifier → TrainingService
    - season_bonus_applied, bonus_ovr_applied → PlayerService (applied after age_players())
    - plan_type → TrainingService (set by manager via /training)
    """
    __tablename__ = "player_development_state"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # XP accumulators — never decremented, only incremented during the season
    training_xp: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    match_xp: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    weeks_trained: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    # Active training plan — set by manager, falls back to club default → "balanced"
    plan_type: Mapped[str] = mapped_column(String(32), server_default="balanced", nullable=False)

    # Current readiness modifier (0.85–1.05). Resets to 1.00 at each new season.
    # Only modifies MatchPlayerInput snapshot — never written to player.fitness.
    readiness_modifier: Mapped[Decimal] = mapped_column(
        Numeric(precision=4, scale=2), server_default="1.00", nullable=False
    )

    # Season-end bonus lifecycle.
    # season_bonus_applied=True means the evaluation ran, even if bonus was 0.
    # This prevents repeated evaluation on retry.
    season_bonus_applied: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    season_bonus_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bonus_ovr_applied: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    player: Mapped["Player"] = relationship("Player", foreign_keys=[player_id])
    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id])

    __table_args__ = (
        UniqueConstraint("player_id", "season_id", name="uq_dev_state_player_season"),
        CheckConstraint("training_xp >= 0", name="chk_dev_state_training_xp"),
        CheckConstraint("match_xp >= 0", name="chk_dev_state_match_xp"),
        CheckConstraint("weeks_trained >= 0", name="chk_dev_state_weeks_trained"),
        CheckConstraint(
            "readiness_modifier >= 0.85 AND readiness_modifier <= 1.05",
            name="chk_dev_state_readiness",
        ),
        CheckConstraint(
            "plan_type IN ('balanced', 'fitness', 'sharpness', 'tactical')",
            name="chk_dev_state_plan_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PlayerDevelopmentState player_id={self.player_id} season_id={self.season_id} "
            f"training_xp={self.training_xp} match_xp={self.match_xp} "
            f"readiness={self.readiness_modifier} bonus_applied={self.season_bonus_applied}>"
        )


class ClubTrainingSettings(Base):
    """
    One row per human club per season. Stores the club-wide default plan and
    training intensity set by the manager via /training.

    Bot clubs never have rows here.
    """
    __tablename__ = "club_training_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Manager-configurable settings
    default_plan: Mapped[str] = mapped_column(String(32), server_default="balanced", nullable=False)
    intensity: Mapped[str] = mapped_column(String(16), server_default="normal", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id])

    __table_args__ = (
        UniqueConstraint("club_id", "season_id", name="uq_training_settings_club_season"),
        CheckConstraint(
            "default_plan IN ('balanced', 'fitness', 'sharpness', 'tactical')",
            name="chk_training_settings_plan",
        ),
        CheckConstraint(
            "intensity IN ('light', 'normal', 'heavy')",
            name="chk_training_settings_intensity",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ClubTrainingSettings club_id={self.club_id} season_id={self.season_id} "
            f"plan={self.default_plan} intensity={self.intensity}>"
        )


class WeeklyTrainingLog(Base):
    """
    Idempotency record for the weekly training tick.

    The UNIQUE constraint on (club_id, player_id, season_id, week) is the
    concurrency gate. The service inserts this row first via
    INSERT ... ON CONFLICT DO NOTHING RETURNING id and only applies XP/stat
    mutations if the insert succeeds (returned a non-None ID).

    Never created for bot clubs or friendly matches.
    """
    __tablename__ = "weekly_training_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    week: Mapped[int] = mapped_column(Integer, nullable=False)

    # What was applied this week
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False)
    intensity: Mapped[str] = mapped_column(String(16), nullable=False)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    sharpness_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    morale_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    readiness_before: Mapped[Decimal] = mapped_column(Numeric(precision=4, scale=2), nullable=False)
    readiness_after: Mapped[Decimal] = mapped_column(Numeric(precision=4, scale=2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "club_id", "player_id", "season_id", "week",
            name="uq_weekly_log_club_player_season_week",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WeeklyTrainingLog player_id={self.player_id} season_id={self.season_id} "
            f"week={self.week} plan={self.plan_type} xp={self.xp_earned}>"
        )


class MatchDevelopmentEvent(Base):
    """
    League-only match XP record. Created inside apply_league_match_consequences().

    Friendlies never create rows here because FriendlyService never calls
    apply_league_match_consequences() — the guarantee is architectural.

    Bot club players never receive rows here (filtered by is_bot_controlled).
    Only players with minutes_played > 0 receive rows.

    The UNIQUE constraint on (player_id, fixture_id) is the concurrency gate —
    used with INSERT ... ON CONFLICT DO NOTHING RETURNING id. match_xp is only
    incremented on the dev_state if the insert succeeds.
    """
    __tablename__ = "match_development_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    fixture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False, index=True)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    minutes_played: Mapped[int] = mapped_column(Integer, nullable=False)
    match_rating: Mapped[Decimal | None] = mapped_column(Numeric(precision=3, scale=1), nullable=True)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("player_id", "fixture_id", name="uq_match_dev_player_fixture"),
    )

    def __repr__(self) -> str:
        return (
            f"<MatchDevelopmentEvent player_id={self.player_id} fixture_id={self.fixture_id} "
            f"minutes={self.minutes_played} xp={self.xp_earned}>"
        )
