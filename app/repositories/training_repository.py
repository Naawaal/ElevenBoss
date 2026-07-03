# app/repositories/training_repository.py

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import and_

from app.models.player_development import (
    PlayerDevelopmentState,
    ClubTrainingSettings,
    WeeklyTrainingLog,
    MatchDevelopmentEvent,
)
from app.models.player import Player
from app.models.club import Club


async def get_or_create_dev_state(
    session: AsyncSession,
    player_id: uuid.UUID,
    season_id: uuid.UUID,
    club_id: uuid.UUID,
    guild_id: str,
) -> PlayerDevelopmentState:
    """
    Retrieves the PlayerDevelopmentState for a player in a season, or creates a new one
    initialized with 'balanced' plan type and 1.00 readiness.
    """
    stmt = select(PlayerDevelopmentState).where(
        and_(
            PlayerDevelopmentState.player_id == player_id,
            PlayerDevelopmentState.season_id == season_id
        )
    )
    res = await session.execute(stmt)
    state = res.scalar_one_or_none()

    if state is None:
        # Create a new one
        state = PlayerDevelopmentState(
            club_id=club_id,
            player_id=player_id,
            season_id=season_id,
            guild_id=guild_id,
            training_xp=0,
            match_xp=0,
            weeks_trained=0,
            plan_type="balanced",
            readiness_modifier=Decimal("1.00"),
            season_bonus_applied=False,
            bonus_ovr_applied=0,
        )
        session.add(state)
        await session.flush()

    return state


async def get_dev_state_map_for_players(
    session: AsyncSession,
    player_ids: list[uuid.UUID],
    season_id: uuid.UUID,
) -> dict[uuid.UUID, PlayerDevelopmentState]:
    """
    Returns a mapping of player_id -> PlayerDevelopmentState for the given list of player IDs in a season.
    """
    if not player_ids:
        return {}

    stmt = select(PlayerDevelopmentState).where(
        and_(
            PlayerDevelopmentState.player_id.in_(player_ids),
            PlayerDevelopmentState.season_id == season_id
        )
    )
    res = await session.execute(stmt)
    states = res.scalars().all()

    return {state.player_id: state for state in states}


async def get_or_create_training_settings(
    session: AsyncSession,
    club_id: uuid.UUID,
    season_id: uuid.UUID,
    guild_id: str,
) -> ClubTrainingSettings:
    """
    Retrieves or creates the ClubTrainingSettings for a club in a season.
    Defaults to 'balanced' default_plan and 'normal' intensity.
    """
    stmt = select(ClubTrainingSettings).where(
        and_(
            ClubTrainingSettings.club_id == club_id,
            ClubTrainingSettings.season_id == season_id
        )
    )
    res = await session.execute(stmt)
    settings = res.scalar_one_or_none()

    if settings is None:
        settings = ClubTrainingSettings(
            club_id=club_id,
            season_id=season_id,
            guild_id=guild_id,
            default_plan="balanced",
            intensity="normal",
        )
        session.add(settings)
        await session.flush()

    return settings


async def get_human_club_players_for_training(
    session: AsyncSession,
    guild_id: str,
    season_id: uuid.UUID,
) -> list[tuple[Club, Player]]:
    """
    Fetches all non-retired players belonging to human-managed clubs in a guild.
    """
    stmt = (
        select(Club, Player)
        .join(Player, Player.club_id == Club.id)
        .where(
            and_(
                Club.guild_id == str(guild_id),
                Club.is_bot_controlled == False,
                Player.is_retired == False
            )
        )
    )
    res = await session.execute(stmt)
    return list(res.all())


async def insert_weekly_training_log_returning_id(
    session: AsyncSession,
    club_id: uuid.UUID,
    player_id: uuid.UUID,
    season_id: uuid.UUID,
    guild_id: str,
    week: int,
    plan_type: str,
    intensity: str,
    xp_earned: int,
    sharpness_delta: int,
    morale_delta: int,
    readiness_before: Decimal,
    readiness_after: Decimal,
    notes: str | None = None,
) -> uuid.UUID | None:
    """
    Inserts a weekly training log using insert-first idempotency (ON CONFLICT DO NOTHING).
    Returns the log ID if inserted, or None if a log already exists for this week.
    """
    stmt = (
        insert(WeeklyTrainingLog)
        .values(
            club_id=club_id,
            player_id=player_id,
            season_id=season_id,
            guild_id=guild_id,
            week=week,
            plan_type=plan_type,
            intensity=intensity,
            xp_earned=xp_earned,
            sharpness_delta=sharpness_delta,
            morale_delta=morale_delta,
            readiness_before=readiness_before,
            readiness_after=readiness_after,
            notes=notes,
        )
        .on_conflict_do_nothing(
            index_elements=["club_id", "player_id", "season_id", "week"]
        )
        .returning(WeeklyTrainingLog.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def insert_match_development_event_returning_id(
    session: AsyncSession,
    club_id: uuid.UUID,
    player_id: uuid.UUID,
    fixture_id: uuid.UUID,
    season_id: uuid.UUID,
    guild_id: str,
    minutes_played: int,
    match_rating: Decimal | None,
    xp_earned: int,
    reason_breakdown: dict | None = None,
) -> uuid.UUID | None:
    """
    Inserts a match development event using insert-first idempotency (ON CONFLICT DO NOTHING).
    Returns the event ID if inserted, or None if a match event already exists for this player/fixture.
    """
    stmt = (
        insert(MatchDevelopmentEvent)
        .values(
            club_id=club_id,
            player_id=player_id,
            fixture_id=fixture_id,
            season_id=season_id,
            guild_id=guild_id,
            minutes_played=minutes_played,
            match_rating=match_rating,
            xp_earned=xp_earned,
            reason_breakdown=reason_breakdown,
        )
        .on_conflict_do_nothing(
            index_elements=["player_id", "fixture_id"]
        )
        .returning(MatchDevelopmentEvent.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_season_dev_states_for_bonus(
    session: AsyncSession,
    season_id: uuid.UUID,
) -> list[PlayerDevelopmentState]:
    """
    Fetches all eligible player development states for season-end OVR training bonuses.
    Filters:
      - Club is human-controlled (Club.is_bot_controlled == False)
      - Player is not retired
      - Player age <= 29 (note: age is already incremented/post-aging since age_players() ran first)
      - season_bonus_applied == False
    """
    stmt = (
        select(PlayerDevelopmentState)
        .join(Player, Player.id == PlayerDevelopmentState.player_id)
        .join(Club, Club.id == PlayerDevelopmentState.club_id)
        .where(
            and_(
                PlayerDevelopmentState.season_id == season_id,
                Club.is_bot_controlled == False,
                Player.is_retired == False,
                Player.age <= 29,
                PlayerDevelopmentState.season_bonus_applied == False
            )
        )
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def mark_bonus_applied(
    session: AsyncSession,
    dev_state_id: uuid.UUID,
    bonus_ovr: int,
) -> None:
    """
    Marks the player's seasonal training bonus as evaluated (season_bonus_applied = True)
    and logs the OVR bonus amount applied (even if 0).
    """
    stmt = select(PlayerDevelopmentState).where(PlayerDevelopmentState.id == dev_state_id)
    res = await session.execute(stmt)
    state = res.scalar_one_or_none()
    if state:
        state.season_bonus_applied = True
        state.season_bonus_applied_at = datetime.utcnow()
        state.bonus_ovr_applied = bonus_ovr
        await session.flush()
