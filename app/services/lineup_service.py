# app/services/lineup_service.py

import logging
import uuid
from dataclasses import dataclass
from app.db.session import get_session
from app.repositories import get_manager_by_discord_id, get_club_by_manager_id, get_players_by_club_id
from app.repositories.lineup_repository import get_active_lineup, save_lineup_with_players
from app.engine.lineup_builder import build_auto_lineup
from app.engine.lineup_validator import validate_lineup
from app.error_reporting import capture_exception

logger = logging.getLogger("app.services.lineup_service")

@dataclass
class LineupResult:
    success: bool
    code: str
    message: str
    club_name: str | None = None
    formation: str | None = None
    starters: dict | None = None          # slot -> Player
    bench: list | None = None             # list of Players
    warnings: list[str] | None = None

class LineupService:
    @staticmethod
    async def get_lineup_screen_data(guild_id: int | str, discord_user_id: int | str) -> LineupResult:
        """
        Fetches the current manager club, active lineup, and squad players.
        """
        try:
            async with get_session() as session:
                manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
                if not manager or not manager.club_id:
                    return LineupResult(
                        success=False,
                        code="NO_CLUB",
                        message="You are not registered as a manager with a club. Run `/register` to get started."
                    )
                
                club = await get_club_by_manager_id(session, guild_id, manager.id)
                if not club:
                    return LineupResult(
                        success=False,
                        code="NO_CLUB",
                        message="Club details not found."
                    )
                
                active_lineup = await get_active_lineup(session, club.id)
                club_players = await get_players_by_club_id(session, club.id)
                
                starters = {}
                bench = []
                formation = "4-4-2"
                
                if active_lineup:
                    formation = active_lineup.formation
                    # Resolve lineup players
                    for lp in active_lineup.lineup_players:
                        if lp.is_starter:
                            starters[lp.slot] = lp.player
                        else:
                            bench.append(lp.player)
                            
                # Sort bench by overall descending
                bench.sort(key=lambda p: p.overall, reverse=True)
                
                logger.info(
                    "lineup_screen_opened: guild_id=%s, discord_user_id=%s, club_id=%s, formation=%s",
                    str(guild_id), str(discord_user_id), str(club.id), formation
                )
                
                return LineupResult(
                    success=True,
                    code="SUCCESS",
                    message="Lineup data loaded.",
                    club_name=club.name,
                    formation=formation,
                    starters=starters,
                    bench=bench,
                    warnings=[]
                )
        except Exception as e:
            logger.error("lineup_error: failed to load lineup screen: %s", e, exc_info=e)
            capture_exception(e)
            return LineupResult(
                success=False,
                code="ERROR",
                message="An unexpected error occurred while loading your lineup."
            )

    @staticmethod
    async def preview_auto_lineup(guild_id: int | str, discord_user_id: int | str, formation: str) -> LineupResult:
        """
        Auto-generates a preview starting XI and bench for a given formation.
        """
        try:
            async with get_session() as session:
                manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
                if not manager or not manager.club_id:
                    return LineupResult(
                        success=False,
                        code="NO_CLUB",
                        message="You are not registered as a manager with a club. Run `/register` to get started."
                    )
                
                club = await get_club_by_manager_id(session, guild_id, manager.id)
                if not club:
                    return LineupResult(
                        success=False,
                        code="NO_CLUB",
                        message="Club details not found."
                    )
                
                players = await get_players_by_club_id(session, club.id)
                if not players:
                    return LineupResult(
                        success=False,
                        code="EMPTY_SQUAD",
                        message="Your squad is empty. You need players to generate a lineup."
                    )
                
                starters, bench, warnings = build_auto_lineup(players, formation)
                
                logger.info(
                    "lineup_auto_generated: guild_id=%s, discord_user_id=%s, club_id=%s, formation=%s",
                    str(guild_id), str(discord_user_id), str(club.id), formation
                )
                
                return LineupResult(
                    success=True,
                    code="SUCCESS",
                    message="Preview lineup generated.",
                    club_name=club.name,
                    formation=formation,
                    starters=starters,
                    bench=bench,
                    warnings=warnings
                )
        except Exception as e:
            logger.error("lineup_error: failed to preview auto lineup: %s", e, exc_info=e)
            capture_exception(e)
            return LineupResult(
                success=False,
                code="ERROR",
                message="An unexpected error occurred while generating the lineup."
            )

    @staticmethod
    async def save_lineup(
        guild_id: int | str,
        discord_user_id: int | str,
        formation: str,
        starters: dict[str, str],  # slot -> player_id string
        bench: list[str]           # player_id string list
    ) -> LineupResult:
        """
        Validates and saves a new active lineup, replacing the previous one.
        """
        try:
            async with get_session() as session:
                manager = await get_manager_by_discord_id(session, guild_id, discord_user_id)
                if not manager or not manager.club_id:
                    return LineupResult(
                        success=False,
                        code="NO_CLUB",
                        message="You are not registered as a manager with a club. Run `/register` to get started."
                    )
                
                club = await get_club_by_manager_id(session, guild_id, manager.id)
                if not club:
                    return LineupResult(
                        success=False,
                        code="NO_CLUB",
                        message="Club details not found."
                    )
                
                club_players = await get_players_by_club_id(session, club.id)
                
                # Run validation
                is_valid, err_msg = validate_lineup(formation, starters, bench, club_players)
                if not is_valid:
                    logger.warning(
                        "lineup_validation_failed: guild_id=%s, discord_user_id=%s, club_id=%s, formation=%s, reason=%s",
                        str(guild_id), str(discord_user_id), str(club.id), formation, err_msg
                    )
                    return LineupResult(
                        success=False,
                        code="VALIDATION_FAILED",
                        message=err_msg
                    )
                
                # Convert player ID strings to UUIDs
                starters_uuid = {slot: uuid.UUID(pid) for slot, pid in starters.items()}
                bench_uuid = [uuid.UUID(pid) for pid in bench]
                
                await save_lineup_with_players(
                    session,
                    guild_id,
                    club.id,
                    formation,
                    starters_uuid,
                    bench_uuid
                )
                
                logger.info(
                    "lineup_saved: guild_id=%s, discord_user_id=%s, club_id=%s, formation=%s",
                    str(guild_id), str(discord_user_id), str(club.id), formation
                )
                
                return LineupResult(
                    success=True,
                    code="SUCCESS",
                    message="Your lineup and formation have been successfully saved!"
                )
        except Exception as e:
            logger.error(
                "lineup_save_failed: guild_id=%s, discord_user_id=%s, formation=%s, error=%s",
                str(guild_id), str(discord_user_id), formation, str(e), exc_info=e
            )
            capture_exception(e)
            return LineupResult(
                success=False,
                code="ERROR",
                message="A database error occurred while saving your lineup. All changes rolled back."
            )
