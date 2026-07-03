# app/services/match_service.py

import logging
import uuid
from dataclasses import dataclass, field

from app.db.session import get_session
from app.repositories import (
    get_latest_played_fixture,
    get_match_result_by_fixture,
    get_match_events,
)
from app.models.fixture import FixtureStatus

logger = logging.getLogger("app.services.match_service")


# ── Result Dataclasses ─────────────────────────────────────────────

@dataclass
class MatchDetailResult:
    success: bool
    code: str
    message: str
    fixture_id: str | None = None
    home_club_name: str | None = None
    away_club_name: str | None = None
    home_goals: int | None = None
    away_goals: int | None = None
    home_possession: int | None = None
    away_possession: int | None = None
    home_shots: int | None = None
    away_shots: int | None = None
    home_shots_on_target: int | None = None
    away_shots_on_target: int | None = None
    motm_player_name: str | None = None
    timeline: list[dict] = field(default_factory=list)


# ── Service Implementation ─────────────────────────────────────────

class MatchService:

    @staticmethod
    async def get_recent_match(
        guild_id: int | str,
    ) -> MatchDetailResult:
        """
        Retrieves details of the most recently played match in the guild.
        """
        logger.info(f"match_recent_viewed: guild_id={guild_id}")
        
        try:
            async with get_session() as session:
                fixture = await get_latest_played_fixture(session, guild_id)
                if not fixture:
                    return MatchDetailResult(
                        success=False,
                        code="no_matches_played",
                        message="No matches have been simulated in this server yet."
                    )
                
                # Fetch details for this fixture
                return await MatchService._hydrate_match_detail(session, guild_id, fixture)
                
        except Exception as e:
            logger.error(f"match_error: failed to load recent match for guild_id={guild_id}: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return MatchDetailResult(
                success=False,
                code="unexpected_error",
                message="An unexpected error occurred while loading the match details."
            )

    @staticmethod
    async def get_match_detail(
        guild_id: int | str,
        fixture_id: str | uuid.UUID,
    ) -> MatchDetailResult:
        """
        Retrieves details of a specific match by fixture_id.
        """
        logger.info(f"match_detail_viewed: guild_id={guild_id}, fixture_id={fixture_id}")
        
        try:
            fid = uuid.UUID(str(fixture_id))
            async with get_session() as session:
                # Fetch fixture
                from sqlalchemy.future import select
                from sqlalchemy.orm import joinedload
                from app.models.fixture import Fixture
                stmt = (
                    select(Fixture)
                    .where(
                        Fixture.guild_id == str(guild_id),
                        Fixture.id == fid
                    )
                    .options(
                        joinedload(Fixture.home_club),
                        joinedload(Fixture.away_club),
                        joinedload(Fixture.match_result)
                    )
                )
                result = await session.execute(stmt)
                fixture = result.scalar_one_or_none()
                
                if not fixture:
                    return MatchDetailResult(
                        success=False,
                        code="match_not_found",
                        message="The requested match details were not found."
                    )
                    
                if fixture.status != FixtureStatus.PLAYED:
                    return MatchDetailResult(
                        success=False,
                        code="match_not_played",
                        message="This fixture has not been simulated yet."
                    )
                    
                return await MatchService._hydrate_match_detail(session, guild_id, fixture)
                
        except Exception as e:
            logger.error(f"match_error: failed to load match details: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return MatchDetailResult(
                success=False,
                code="unexpected_error",
                message="An unexpected error occurred while loading the match details."
            )

    @staticmethod
    async def _hydrate_match_detail(session, guild_id, fixture) -> MatchDetailResult:
        res = await get_match_result_by_fixture(session, guild_id, fixture.id)
        if not res:
            return MatchDetailResult(
                success=False,
                code="match_result_missing",
                message="Match statistics are missing."
            )
            
        events = await get_match_events(session, guild_id, fixture.id)
        
        timeline_list = []
        for e in events:
            # Map events to list of serializable dicts
            timeline_list.append({
                "minute": e.minute,
                "type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                "description": e.description,
                "player_name": e.player.display_name if e.player else None,
                "secondary_player_name": e.secondary_player.display_name if e.secondary_player else None,
            })
            
        # Sort timeline chronologically, with secondary priority for same-minute events
        def event_sort_key(item):
            minute = item["minute"]
            etype = item["type"]
            priority_map = {
                "match_start": 0,
                "goal": 10,
                "yellow_card": 20,
                "red_card": 21,
                "injury": 30,
                "substitution": 31,
                "half_time": 90,
                "full_time": 100,
            }
            return (minute, priority_map.get(etype, 50))
            
        timeline_list.sort(key=event_sort_key)
        
        motm_name = res.motm_player.display_name if res.motm_player else "None"
        
        return MatchDetailResult(
            success=True,
            code="success",
            message="Match details loaded successfully.",
            fixture_id=str(fixture.id),
            home_club_name=fixture.home_club.name,
            away_club_name=fixture.away_club.name,
            home_goals=res.home_goals,
            away_goals=res.away_goals,
            home_possession=res.home_possession,
            away_possession=res.away_possession,
            home_shots=res.home_shots,
            away_shots=res.away_shots,
            home_shots_on_target=res.home_shots_on_target,
            away_shots_on_target=res.away_shots_on_target,
            motm_player_name=motm_name,
            timeline=timeline_list
        )
