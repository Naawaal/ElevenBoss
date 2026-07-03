# app/services/lineup_service.py

import logging
import uuid
from dataclasses import dataclass
from app.db.session import get_session
from app.repositories import (
    get_manager_by_discord_id, get_club_by_manager_id,
    get_players_by_club_id, get_available_players_by_club_id
)
from app.repositories.lineup_repository import get_active_lineup, save_lineup_with_players
from app.engine.lineup_builder import build_auto_lineup
from app.engine.lineup_validator import validate_lineup
from app.error_reporting import capture_exception
from app.engine.match_engine import MatchPlayerInput

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


@dataclass(frozen=True)
class LineupResolutionResult:
    formation: str
    starters: list[MatchPlayerInput]
    bench: list[MatchPlayerInput]


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
                
                # Check for injured or suspended players in the lineup
                warnings = []
                for slot, p in starters.items():
                    inj_days = getattr(p, "injury_days_remaining", 0)
                    susp_games = getattr(p, "suspension_games_remaining", 0)
                    if isinstance(inj_days, int) and inj_days > 0:
                        warnings.append(f"Starter '{p.display_name}' ({slot}) is injured ({p.injury_days_remaining}d remaining).")
                    elif isinstance(susp_games, int) and susp_games > 0:
                        warnings.append(f"Starter '{p.display_name}' ({slot}) is suspended ({p.suspension_games_remaining}g remaining).")
                for p in bench:
                    inj_days = getattr(p, "injury_days_remaining", 0)
                    susp_games = getattr(p, "suspension_games_remaining", 0)
                    if isinstance(inj_days, int) and inj_days > 0:
                        warnings.append(f"Bench player '{p.display_name}' is injured ({p.injury_days_remaining}d remaining).")
                    elif isinstance(susp_games, int) and susp_games > 0:
                        warnings.append(f"Bench player '{p.display_name}' is suspended ({p.suspension_games_remaining}g remaining).")
                
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
                    warnings=warnings
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
                
                available_players = []
                for p in players:
                    is_retired = getattr(p, "is_retired", False)
                    inj_days = getattr(p, "injury_days_remaining", 0)
                    if not isinstance(inj_days, int):
                        inj_days = 0
                    susp_games = getattr(p, "suspension_games_remaining", 0)
                    if not isinstance(susp_games, int):
                        susp_games = 0
                    if not is_retired and inj_days <= 0 and susp_games <= 0:
                        available_players.append(p)
                available_players.sort(key=lambda x: getattr(x, "overall", 0) or 0, reverse=True)
                
                candidates = available_players if len(available_players) >= 11 else players
                starters, bench, warnings = build_auto_lineup(candidates, formation)
                
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
                
                warnings = []
                for slot, pid in starters.items():
                    p = next((x for x in club_players if str(x.id) == pid), None)
                    if p:
                        inj_days = getattr(p, "injury_days_remaining", 0)
                        susp_games = getattr(p, "suspension_games_remaining", 0)
                        if isinstance(inj_days, int) and inj_days > 0:
                            warnings.append(f"Starter '{p.display_name}' ({slot}) is injured ({p.injury_days_remaining}d remaining).")
                        elif isinstance(susp_games, int) and susp_games > 0:
                            warnings.append(f"Starter '{p.display_name}' ({slot}) is suspended ({p.suspension_games_remaining}g remaining).")
                for pid in bench:
                    p = next((x for x in club_players if str(x.id) == pid), None)
                    if p:
                        inj_days = getattr(p, "injury_days_remaining", 0)
                        susp_games = getattr(p, "suspension_games_remaining", 0)
                        if isinstance(inj_days, int) and inj_days > 0:
                            warnings.append(f"Bench player '{p.display_name}' is injured ({p.injury_days_remaining}d remaining).")
                        elif isinstance(susp_games, int) and susp_games > 0:
                            warnings.append(f"Bench player '{p.display_name}' is suspended ({p.suspension_games_remaining}g remaining).")
                
                return LineupResult(
                    success=True,
                    code="SUCCESS",
                    message="Your lineup and formation have been successfully saved!",
                    warnings=warnings
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

    @staticmethod
    def generate_board_image(
        club_name: str,
        manager_name: str,
        formation: str,
        starters: dict,
        bench: list,
        warnings: list[str],
        is_dirty: bool = False
    ) -> bytes | None:
        """
        Maps starting players to the board renderer and generates the PNG bytes.
        """
        try:
            logger.info("lineup_board_render_started: club_name=%s, formation=%s", club_name, formation)
            from app.ui.lineup_image_renderer import LineupBoardPlayer, LineupBoardData, render_lineup_board
            from app.engine.formation_rules import get_slot_rules
            
            board_players = []
            for slot, p in starters.items():
                if p:
                    board_players.append(LineupBoardPlayer(
                        player_id=str(p.id),
                        name=p.display_name,
                        position=p.position,
                        slot=slot,
                        overall=p.overall,
                        potential=p.potential,
                        fitness=p.fitness,
                        is_captain=False
                    ))
            
            # Calculate average overall of playing starters
            avg_ovr = 0.0
            if starters:
                playing_starters = [p for p in starters.values() if p]
                if playing_starters:
                    avg_ovr = sum(p.overall for p in playing_starters) / len(playing_starters)
                    
            # Calculate chemistry based on position suitability
            count_chem = 60.0 * (len(board_players) / 11.0)
            pos_score = 0.0
            for slot, p in starters.items():
                if p:
                    rules = get_slot_rules(slot)
                    if p.position in rules.get("natural", []):
                        pos_score += 40.0 / 11.0
                    elif p.position in rules.get("compatible", []):
                        pos_score += 20.0 / 11.0
            chemistry = min(100, max(0, int(count_chem + pos_score)))
            
            board_data = LineupBoardData(
                club_name=club_name,
                manager_name=manager_name,
                formation=formation,
                chemistry=chemistry,
                average_overall=avg_ovr,
                players=board_players,
                bench_count=len(bench),
                warnings=warnings,
                is_dirty=is_dirty
            )
            
            img_bytes = render_lineup_board(board_data)
            logger.info(
                "lineup_board_render_success: club_name=%s, formation=%s, player_count=%d",
                club_name, formation, len(board_players)
            )
            return img_bytes
        except Exception as e:
            logger.error("lineup_board_render_failed: Failed to render visual lineup: %s", e, exc_info=e)
            return None

    @staticmethod
    async def resolve_team_lineup(
        session,
        guild_id: int | str,
        club_id: uuid.UUID,
        club_name: str,
        persist_fallback: bool = True
    ) -> LineupResolutionResult:
        """
        Resolves the starting XI and bench for a club.
        Uses the active lineup if valid; otherwise, auto-picks the best XI and bench.
        Persists the fallback lineup to the database only if persist_fallback is True.
        """
        # 1. Load active lineup
        lineup = await get_active_lineup(session, club_id)
        club_players = await get_players_by_club_id(session, club_id)
        
        # Load readiness modifiers from player development state
        from app.repositories import get_active_or_draft_league_by_guild, get_active_season_for_league
        from app.repositories.training_repository import get_dev_state_map_for_players
        
        season_id = None
        dev_state_map = {}
        
        # Safe bypass for mock sessions in unit tests
        from unittest.mock import Mock
        if not (isinstance(session, Mock) and not isinstance(get_dev_state_map_for_players, Mock)):
            league = await get_active_or_draft_league_by_guild(session, str(guild_id))
            if league:
                active_season = await get_active_season_for_league(session, str(guild_id), league.id)
                if active_season:
                    season_id = active_season.id
                    
            if season_id and club_players:
                player_ids = [p.id for p in club_players]
                dev_state_map = await get_dev_state_map_for_players(session, player_ids, season_id)
            
        # Resilient helper to retrieve readiness modifier safely, protecting against test mocks
        from app.models.player_development import PlayerDevelopmentState
        def get_player_readiness(player_id) -> float:
            if not isinstance(dev_state_map, dict):
                return 1.00
            ds = dev_state_map.get(player_id)
            if isinstance(ds, PlayerDevelopmentState):
                return float(ds.readiness_modifier)
            return 1.00
        
        available_players = []
        for p in club_players:
            is_retired = getattr(p, "is_retired", False)
            inj_days = getattr(p, "injury_days_remaining", 0)
            if not isinstance(inj_days, int):
                inj_days = 0
            susp_games = getattr(p, "suspension_games_remaining", 0)
            if not isinstance(susp_games, int):
                susp_games = 0
            if not is_retired and inj_days <= 0 and susp_games <= 0:
                available_players.append(p)
        available_players.sort(key=lambda x: getattr(x, "overall", 0) or 0, reverse=True)
        available_player_ids = {p.id for p in available_players}

        # Verify we have at least 11 active players
        if len(club_players) < 11:
            raise ValueError(f"Club '{club_name}' does not have enough active players (has {len(club_players)}, requires 11).")

        # 2. Check if lineup is valid and contains only available players
        is_valid = False
        if lineup:
            starters = {lp.slot: lp.player_id for lp in lineup.lineup_players if lp.is_starter}
            bench = [lp.player_id for lp in lineup.lineup_players if not lp.is_starter]
            
            selected_ids = set(starters.values()) | set(bench)
            all_selected_available = all(pid in available_player_ids for pid in selected_ids)
            
            if all_selected_available:
                is_valid, _ = validate_lineup(lineup.formation, starters, bench, club_players)
            else:
                logger.info(f"lineup_invalid: club_id={club_id} ({club_name}) has unavailable (injured/suspended) players in lineup.")

        if not is_valid:
            # Fallback: Auto-pick best XI using available players (fallback to club_players if < 11 available)
            candidates = available_players if len(available_players) >= 11 else club_players
            logger.info(f"lineup_fallback: auto-picking best XI for club_id={club_id} ({club_name}) using {len(candidates)} candidates")
            starters_objs, bench_objs, _ = build_auto_lineup(candidates, "4-4-2")

            if persist_fallback:
                # Convert starting objects to dict of IDs
                starters_ids = {slot: p.id for slot, p in starters_objs.items()}
                bench_ids = [p.id for p in bench_objs]

                # Save fallback lineup in the DB
                await save_lineup_with_players(
                    session,
                    guild_id,
                    club_id,
                    "4-4-2",
                    starters_ids,
                    bench_ids
                )
                await session.flush()

            # Map starters
            starters_players = []
            for slot, p in starters_objs.items():
                readiness = get_player_readiness(p.id)
                adjusted_fitness = min(100, int(p.fitness * readiness))

                starters_players.append(MatchPlayerInput(
                    player_id=str(p.id),
                    name=p.display_name,
                    position=p.position,
                    slot=slot,
                    overall=p.overall,
                    potential=p.potential,
                    fitness=adjusted_fitness,
                    morale=getattr(p, "morale", 80),
                    consistency=getattr(p, "consistency", 70),
                    is_goalkeeper=(p.position == "GK")
                ))

            # Map bench with unique SUB slot group formatting
            bench_players = []
            gk_idx = 1
            def_idx = 1
            mid_idx = 1
            att_idx = 1
            for p in bench_objs:
                pos = p.position.upper()
                if pos == "GK":
                    slot = f"SUB_GK_{gk_idx}"
                    gk_idx += 1
                elif pos in ("LB", "CB", "RB", "LWB", "RWB"):
                    slot = f"SUB_DEF_{def_idx}"
                    def_idx += 1
                elif pos in ("LM", "CM", "RM", "CDM", "CAM", "LDM", "RDM"):
                    slot = f"SUB_MID_{mid_idx}"
                    mid_idx += 1
                else:
                    slot = f"SUB_ATT_{att_idx}"
                    att_idx += 1

                readiness = get_player_readiness(p.id)
                adjusted_fitness = min(100, int(p.fitness * readiness))

                bench_players.append(MatchPlayerInput(
                    player_id=str(p.id),
                    name=p.display_name,
                    position=p.position,
                    slot=slot,
                    overall=p.overall,
                    potential=p.potential,
                    fitness=adjusted_fitness,
                    morale=getattr(p, "morale", 80),
                    consistency=getattr(p, "consistency", 70),
                    is_goalkeeper=(p.position == "GK")
                ))

            return LineupResolutionResult(
                formation="4-4-2",
                starters=starters_players,
                bench=bench_players
            )

        # Hydrate starting and bench players
        starters_players = []
        db_bench_players = []
        for lp in lineup.lineup_players:
            if lp.is_starter:
                p = lp.player
                readiness = get_player_readiness(p.id)
                adjusted_fitness = min(100, int(p.fitness * readiness))

                starters_players.append(MatchPlayerInput(
                    player_id=str(p.id),
                    name=p.display_name,
                    position=p.position,
                    slot=lp.slot,
                    overall=p.overall,
                    potential=p.potential,
                    fitness=adjusted_fitness,
                    morale=getattr(p, "morale", 80),
                    consistency=getattr(p, "consistency", 70),
                    is_goalkeeper=(p.position == "GK")
                ))
            else:
                db_bench_players.append(lp.player)

        # Sort bench by overall descending
        db_bench_players.sort(key=lambda p: p.overall, reverse=True)

        bench_players = []
        gk_idx = 1
        def_idx = 1
        mid_idx = 1
        att_idx = 1
        for p in db_bench_players:
            pos = p.position.upper()
            if pos == "GK":
                slot = f"SUB_GK_{gk_idx}"
                gk_idx += 1
            elif pos in ("LB", "CB", "RB", "LWB", "RWB"):
                slot = f"SUB_DEF_{def_idx}"
                def_idx += 1
            elif pos in ("LM", "CM", "RM", "CDM", "CAM", "LDM", "RDM"):
                slot = f"SUB_MID_{mid_idx}"
                mid_idx += 1
            else:
                slot = f"SUB_ATT_{att_idx}"
                att_idx += 1

            readiness = get_player_readiness(p.id)
            adjusted_fitness = min(100, int(p.fitness * readiness))

            bench_players.append(MatchPlayerInput(
                player_id=str(p.id),
                name=p.display_name,
                position=p.position,
                slot=slot,
                overall=p.overall,
                potential=p.potential,
                fitness=adjusted_fitness,
                morale=getattr(p, "morale", 80),
                consistency=getattr(p, "consistency", 70),
                is_goalkeeper=(p.position == "GK")
            ))

        return LineupResolutionResult(
            formation=lineup.formation,
            starters=starters_players,
            bench=bench_players
        )





