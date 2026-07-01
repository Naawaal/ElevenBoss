# app/repositories/match_repository.py

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from app.models.match import MatchResult, MatchEvent

async def create_match_result(
    session: AsyncSession,
    guild_id: int | str,
    fixture_id: uuid.UUID,
    home_club_id: uuid.UUID,
    away_club_id: uuid.UUID,
    home_goals: int,
    away_goals: int,
    home_possession: int,
    away_possession: int,
    home_shots: int,
    away_shots: int,
    home_shots_on_target: int,
    away_shots_on_target: int,
    motm_player_id: uuid.UUID | None = None
) -> MatchResult:
    """
    Creates and persists a MatchResult record.
    """
    res = MatchResult(
        guild_id=str(guild_id),
        fixture_id=fixture_id,
        home_club_id=home_club_id,
        away_club_id=away_club_id,
        home_goals=home_goals,
        away_goals=away_goals,
        home_possession=home_possession,
        away_possession=away_possession,
        home_shots=home_shots,
        away_shots=away_shots,
        home_shots_on_target=home_shots_on_target,
        away_shots_on_target=away_shots_on_target,
        motm_player_id=motm_player_id
    )
    session.add(res)
    return res

async def bulk_create_match_events(
    session: AsyncSession,
    events: list[MatchEvent]
) -> list[MatchEvent]:
    """
    Bulk inserts MatchEvent objects.
    """
    session.add_all(events)
    return events

async def get_match_result_by_fixture(
    session: AsyncSession,
    guild_id: int | str,
    fixture_id: uuid.UUID
) -> MatchResult | None:
    """
    Get the match result for a given fixture, eagerloading the MOTM player.
    """
    stmt = (
        select(MatchResult)
        .where(
            MatchResult.guild_id == str(guild_id),
            MatchResult.fixture_id == fixture_id
        )
        .options(
            joinedload(MatchResult.motm_player)
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_match_events(
    session: AsyncSession,
    guild_id: int | str,
    fixture_id: uuid.UUID
) -> list[MatchEvent]:
    """
    Get all timeline events for a match, sorted by minute ascending.
    """
    stmt = (
        select(MatchEvent)
        .where(
            MatchEvent.guild_id == str(guild_id),
            MatchEvent.fixture_id == fixture_id
        )
        .options(
            joinedload(MatchEvent.player),
            joinedload(MatchEvent.secondary_player)
        )
        .order_by(MatchEvent.minute.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
