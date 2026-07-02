# app/services/matchday_service.py

import logging
import uuid
import hashlib
import traceback
from datetime import datetime
from dataclasses import dataclass, field

from app.db.session import get_session
from app.repositories import (
    get_active_league_by_guild,
    get_active_season_for_league,
    get_current_week_fixtures_for_update,
    get_week_fixture_counts,
    get_fixtures_by_week,
    get_clubs_in_league,
    get_players_by_club_id,
    get_active_lineup,
    save_lineup_with_players,
    create_match_result,
    bulk_create_match_events,
    get_standing_for_update,
    get_fixture_week_range,
    create_running_job,
    mark_job_success,
    mark_job_failed,
    get_job_by_key,
    mark_fixture_played,
)
from app.engine.lineup_builder import build_auto_lineup
from app.engine.lineup_validator import validate_lineup
from app.engine.match_engine import (
    simulate_match,
    MatchPlayerInput,
    MatchTeamInput,
    MatchSimulationInput,
)
from app.models.fixture import Fixture, FixtureStatus
from app.models.match import MatchEvent, MatchEventType
from app.models.season import SeasonStatus
from app.models.league import LeagueStatus
from app.models.scheduler_run import SchedulerRunStatus

logger = logging.getLogger("app.services.matchday_service")


# ── Result Dataclasses ─────────────────────────────────────────────

@dataclass
class MatchdayStatusResult:
    success: bool
    code: str
    message: str
    league_name: str | None = None
    season_number: int | None = None
    current_week: int | None = None
    total_fixtures: int = 0
    scheduled_fixtures: int = 0
    played_fixtures: int = 0
    status_label: str | None = None  # Ready, Played, Complete, etc.


@dataclass
class MatchdayFixtureResult:
    fixture_id: str
    home_club_name: str
    away_club_name: str
    home_goals: int
    away_goals: int
    status: str


@dataclass
class MatchdayRunResult:
    success: bool
    code: str
    message: str
    league_name: str | None = None
    season_number: int | None = None
    simulated_week: int | None = None
    results: list[MatchdayFixtureResult] = field(default_factory=list)
    table_updated: bool = False
    season_completed: bool = False
    winner_name: str | None = None


# ── Service Implementation ─────────────────────────────────────────

class MatchdayService:

    @staticmethod
    async def get_matchday_status(
        guild_id: int | str,
    ) -> MatchdayStatusResult:
        """
        Gets the current week simulation status for the guild's active league/season.
        """
        logger.info(f"matchday_status_viewed: guild_id={guild_id}")
        
        try:
            async with get_session() as session:
                league = await get_active_league_by_guild(session, guild_id)
                if not league:
                    return MatchdayStatusResult(
                        success=False,
                        code="league_not_found",
                        message="No active league found in this server. Start the league first with `/league start`."
                    )
                    
                season = await get_active_season_for_league(session, guild_id, league.id)
                if not season:
                    return MatchdayStatusResult(
                        success=False,
                        code="season_not_found",
                        message="No active season found. Setup the league first."
                    )
                    
                current_week = season.current_week
                counts = await get_week_fixture_counts(session, guild_id, season.id, current_week)
                
                total = counts.get("total", 0)
                played = counts.get("played", 0)
                scheduled = counts.get("scheduled", 0)
                
                # Determine status label
                if season.status == SeasonStatus.COMPLETED or league.status == LeagueStatus.COMPLETED:
                    status_label = "Season Complete"
                elif total == 0:
                    status_label = "No Fixtures"
                elif played == total:
                    status_label = "Already Played"
                else:
                    status_label = "Ready"
                    
                return MatchdayStatusResult(
                    success=True,
                    code="success",
                    message="Matchday status loaded successfully.",
                    league_name=league.name,
                    season_number=season.season_number,
                    current_week=current_week,
                    total_fixtures=total,
                    scheduled_fixtures=scheduled,
                    played_fixtures=played,
                    status_label=status_label
                )
                
        except Exception as e:
            logger.error(f"matchday_error: failed to load status for guild_id={guild_id}: {e}", exc_info=e)
            from app.error_reporting import capture_exception
            capture_exception(e)
            return MatchdayStatusResult(
                success=False,
                code="unexpected_error",
                message="An unexpected error occurred while loading matchday status."
            )

    @staticmethod
    async def run_current_matchday(
        guild_id: int | str,
        discord_user_id: int | str,
        is_admin: bool = False,
    ) -> MatchdayRunResult:
        """
        Runs the simulation for all scheduled fixtures in the guild's current week.
        Executes atomically in a single session.
        """
        logger.info(f"matchday_run_started: guild_id={guild_id}, user_id={discord_user_id}")
        
        # 1. Validate permissions
        if not is_admin:
            logger.warning(f"matchday_run_rejected: reason=permission_denied, guild_id={guild_id}, user_id={discord_user_id}")
            return MatchdayRunResult(
                success=False,
                code="permission_denied",
                message="Only server administrators or game admins can simulate the matchday."
            )
            
        job_key = None
        try:
            # Step 1: Pre-transaction validation of league and season
            async with get_session() as session:
                league = await get_active_league_by_guild(session, guild_id)
                if not league:
                    return MatchdayRunResult(
                        success=False,
                        code="league_not_found",
                        message="No active league found in this server."
                    )
                    
                season = await get_active_season_for_league(session, guild_id, league.id)
                if not season:
                    return MatchdayRunResult(
                        success=False,
                        code="season_not_found",
                        message="No active season found for this league."
                    )
                    
                current_week = season.current_week
                season_id = season.id
                league_name = league.name
                season_number = season.season_number

            # Job key for idempotency
            job_key = f"matchday:{guild_id}:{season_id}:{current_week}"
            
            # Step 2: Open atomic transaction
            async with get_session() as session:
                # Eagerly load/lock league and season for the transaction
                stmt_l = get_active_league_by_guild(session, guild_id)
                league = await stmt_l
                stmt_s = get_active_season_for_league(session, guild_id, league.id)
                season = await stmt_s
                
                # Check if job was already run successfully
                existing_job = await get_job_by_key(session, job_key)
                if existing_job and existing_job.status == SchedulerRunStatus.SUCCESS:
                    logger.info(f"matchday_run_rejected: reason=duplicate_run, job_key={job_key}")
                    return MatchdayRunResult(
                        success=False,
                        code="matchday_already_played",
                        message=f"Week {current_week} matches have already been simulated."
                    )
                elif existing_job and existing_job.status == SchedulerRunStatus.RUNNING:
                    logger.info(f"matchday_run_rejected: reason=job_in_progress, job_key={job_key}")
                    return MatchdayRunResult(
                        success=False,
                        code="matchday_in_progress",
                        message=f"Week {current_week} simulation is already in progress."
                    )
                    
                # Setup job run lock
                job = await create_running_job(
                    session=session,
                    job_key=job_key,
                    job_type="matchday_simulation",
                    guild_id=guild_id,
                    metadata={"week": current_week, "season_number": season.season_number}
                )
                await session.flush()
                logger.info(f"matchday_job_created: job_key={job_key}")
                
                # Lock fixtures
                fixtures = await get_current_week_fixtures_for_update(session, guild_id, season.id, current_week)
                if not fixtures:
                    await mark_job_failed(session, job_key, "No fixtures found for current week.")
                    logger.info(f"matchday_run_rejected: reason=no_fixtures, guild_id={guild_id}, week={current_week}")
                    return MatchdayRunResult(
                        success=False,
                        code="fixtures_not_found",
                        message=f"No fixtures were found for Week {current_week}."
                    )
                    
                # Check if any is already played
                if any(f.status == FixtureStatus.PLAYED for f in fixtures):
                    await mark_job_failed(session, job_key, "Some fixtures already marked played.")
                    return MatchdayRunResult(
                        success=False,
                        code="matchday_already_played",
                        message="Some matches this week have already been simulated."
                    )
                    
                results_list = []
                
                # Simulate each fixture
                for fixture in fixtures:
                    home_club = fixture.home_club
                    away_club = fixture.away_club
                    
                    # Lineup resolving
                    async def resolve_team_lineup(club_id: uuid.UUID, club_name: str) -> tuple[str, list[MatchPlayerInput]]:
                        # 1. Load active lineup
                        lineup = await get_active_lineup(session, club_id)
                        club_players = await get_players_by_club_id(session, club_id)
                        
                        # Verify we have at least 11 active players
                        active_players = [p for p in club_players if not p.is_retired]
                        if len(active_players) < 11:
                            raise ValueError(f"Club '{club_name}' does not have enough active players (has {len(active_players)}, requires 11).")
                            
                        # 2. Check if lineup is valid
                        is_valid = False
                        if lineup:
                            starters = {lp.slot: lp.player_id for lp in lineup.lineup_players if lp.is_starter}
                            bench = [lp.player_id for lp in lineup.lineup_players if not lp.is_starter]
                            is_valid, _ = validate_lineup(lineup.formation, starters, bench, club_players)
                            
                        if not is_valid:
                            # Fallback: Auto-pick best XI
                            logger.info(f"lineup_fallback: auto-picking best XI for club_id={club_id} ({club_name})")
                            starters_objs, bench_objs, _ = build_auto_lineup(club_players, "4-4-2")
                            
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
                            
                            # Build starters_players directly from starters_objs in memory
                            # to avoid database lazy loading issues
                            starters_players = []
                            for slot, p in starters_objs.items():
                                starters_players.append(MatchPlayerInput(
                                    player_id=str(p.id),
                                    name=p.display_name,
                                    position=p.position,
                                    slot=slot,
                                    overall=p.overall,
                                    potential=p.potential,
                                    fitness=p.fitness,
                                    morale=getattr(p, "morale", 80),
                                    is_goalkeeper=(p.position == "GK")
                                ))
                            return "4-4-2", starters_players
                            
                        # Hydrate starting players
                        starters_players = []
                        for lp in lineup.lineup_players:
                            if lp.is_starter:
                                p = lp.player
                                starters_players.append(MatchPlayerInput(
                                    player_id=str(p.id),
                                    name=p.display_name,
                                    position=p.position,
                                    slot=lp.slot,
                                    overall=p.overall,
                                    potential=p.potential,
                                    fitness=p.fitness,
                                    morale=getattr(p, "morale", 80),
                                    is_goalkeeper=(p.position == "GK")
                                ))
                        return lineup.formation, starters_players

                        
                    try:
                        home_formation, home_starters = await resolve_team_lineup(home_club.id, home_club.name)
                        away_formation, away_starters = await resolve_team_lineup(away_club.id, away_club.name)
                    except ValueError as ve:
                        await mark_job_failed(session, job_key, str(ve))
                        logger.warning(f"matchday_run_rejected: reason=lineup_resolution_failed: {ve}")
                        return MatchdayRunResult(
                            success=False,
                            code="invalid_lineup",
                            message=str(ve)
                        )
                        
                    # Deterministic seed generation
                    seed_str = f"{guild_id}:{season_id}:{fixture.id}:{current_week}"
                    seed = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
                    
                    home_team_input = MatchTeamInput(
                        club_id=str(home_club.id),
                        club_name=home_club.name,
                        formation=home_formation,
                        players=home_starters,
                        is_home=True
                    )
                    away_team_input = MatchTeamInput(
                        club_id=str(away_club.id),
                        club_name=away_club.name,
                        formation=away_formation,
                        players=away_starters,
                        is_home=False
                    )
                    sim_input = MatchSimulationInput(
                        fixture_id=str(fixture.id),
                        week=current_week,
                        home_team=home_team_input,
                        away_team=away_team_input,
                        seed=seed
                    )
                    
                    logger.info(f"match_simulation_started: fixture_id={fixture.id}")
                    sim_result = simulate_match(sim_input)
                    logger.info(f"match_simulated: fixture_id={fixture.id}, score={sim_result.home_goals}-{sim_result.away_goals}")
                    
                    # Persist Fixture update
                    await mark_fixture_played(session, fixture.id, sim_result.home_goals, sim_result.away_goals, str(seed))
                    
                    # Create MatchResult
                    await create_match_result(
                        session=session,
                        guild_id=guild_id,
                        fixture_id=fixture.id,
                        home_club_id=home_club.id,
                        away_club_id=away_club.id,
                        home_goals=sim_result.home_goals,
                        away_goals=sim_result.away_goals,
                        home_possession=sim_result.home_possession,
                        away_possession=sim_result.away_possession,
                        home_shots=sim_result.home_shots,
                        away_shots=sim_result.away_shots,
                        home_shots_on_target=sim_result.home_shots_on_target,
                        away_shots_on_target=sim_result.away_shots_on_target,
                        motm_player_id=uuid.UUID(sim_result.motm_player_id) if sim_result.motm_player_id else None
                    )
                    logger.info(f"match_result_saved: fixture_id={fixture.id}")
                    
                    # Create MatchEvents
                    events_list = []
                    # Match start
                    events_list.append(MatchEvent(
                        guild_id=str(guild_id),
                        fixture_id=fixture.id,
                        minute=0,
                        event_type=MatchEventType.MATCH_START,
                        description=f"The referee blows the whistle and the match between {home_club.name} and {away_club.name} begins!"
                    ))
                    # Half time
                    events_list.append(MatchEvent(
                        guild_id=str(guild_id),
                        fixture_id=fixture.id,
                        minute=45,
                        event_type=MatchEventType.HALF_TIME,
                        description=f"Half-Time: {home_club.name} {sim_result.home_goals}–{sim_result.away_goals} {away_club.name}."
                    ))
                    # Full time
                    events_list.append(MatchEvent(
                        guild_id=str(guild_id),
                        fixture_id=fixture.id,
                        minute=90,
                        event_type=MatchEventType.FULL_TIME,
                        description=f"Full-Time: The referee blows the final whistle. Final score: {home_club.name} {sim_result.home_goals}–{sim_result.away_goals} {away_club.name}."
                    ))
                    # Goals
                    for g in sim_result.goals:
                        events_list.append(MatchEvent(
                            guild_id=str(guild_id),
                            fixture_id=fixture.id,
                            minute=g.minute,
                            event_type=MatchEventType.GOAL,
                            club_id=uuid.UUID(g.club_id),
                            player_id=uuid.UUID(g.scorer_id),
                            secondary_player_id=uuid.UUID(g.assist_id) if g.assist_id else None,
                            description=g.description
                        ))
                    # Cards
                    for c in sim_result.cards:
                        events_list.append(MatchEvent(
                            guild_id=str(guild_id),
                            fixture_id=fixture.id,
                            minute=c.minute,
                            event_type=MatchEventType.RED_CARD if c.card_type == "red" else MatchEventType.YELLOW_CARD,
                            club_id=uuid.UUID(c.club_id),
                            player_id=uuid.UUID(c.player_id),
                            description=c.description
                        ))
                    await bulk_create_match_events(session, events_list)
                    logger.info(f"match_events_saved: fixture_id={fixture.id}, count={len(events_list)}")
                    
                    # Update standings
                    home_standing = await get_standing_for_update(session, guild_id, season.id, home_club.id)
                    away_standing = await get_standing_for_update(session, guild_id, season.id, away_club.id)
                    
                    if home_standing and away_standing:
                        home_standing.played += 1
                        away_standing.played += 1
                        
                        home_standing.goals_for += sim_result.home_goals
                        home_standing.goals_against += sim_result.away_goals
                        away_standing.goals_for += sim_result.away_goals
                        away_standing.goals_against += sim_result.home_goals
                        
                        home_standing.goal_difference = home_standing.goals_for - home_standing.goals_against
                        away_standing.goal_difference = away_standing.goals_for - away_standing.goals_against
                        
                        if sim_result.home_goals > sim_result.away_goals:
                            home_standing.wins += 1
                            home_standing.points += 3
                            away_standing.losses += 1
                        elif sim_result.away_goals > sim_result.home_goals:
                            away_standing.wins += 1
                            away_standing.points += 3
                            home_standing.losses += 1
                        else:
                            home_standing.draws += 1
                            home_standing.points += 1
                            away_standing.draws += 1
                            away_standing.points += 1
                            
                    results_list.append(MatchdayFixtureResult(
                        fixture_id=str(fixture.id),
                        home_club_name=home_club.name,
                        away_club_name=away_club.name,
                        home_goals=sim_result.home_goals,
                        away_goals=sim_result.away_goals,
                        status="played"
                    ))
                    
                logger.info(f"standings_updated: guild_id={guild_id}, season_id={season.id}")
                
                # Advance Season Week
                week_range = await get_fixture_week_range(session, guild_id, season.id)
                max_week = week_range[1] if week_range else current_week
                
                season_completed = False
                winner_name = None
                if current_week == max_week:
                     season.status = SeasonStatus.COMPLETED
                     season.ended_at = datetime.utcnow()
                     league.status = LeagueStatus.COMPLETED
                     season_completed = True
                     logger.info(f"season_completed: guild_id={guild_id}, season_id={season.id}")
                     
                     from app.repositories.standing_repository import get_ranked_table
                     standings = await get_ranked_table(session, guild_id, season.id)
                     winner_name = standings[0].club.name if standings else None
                else:
                     season.current_week += 1
                     logger.info(f"season_week_advanced: guild_id={guild_id}, season_id={season.id}, next_week={season.current_week}")
                     
                # Mark job success
                await mark_job_success(session, job_key)
                
                logger.info(f"matchday_run_success: guild_id={guild_id}, week={current_week}")
                
                return MatchdayRunResult(
                    success=True,
                    code="success",
                    message=f"Week {current_week} matches simulated successfully!",
                    league_name=league_name,
                    season_number=season_number,
                    simulated_week=current_week,
                    results=results_list,
                    table_updated=True,
                    season_completed=season_completed,
                    winner_name=winner_name
                )
                
        except Exception as e:
            err_trace = traceback.format_exc()
            logger.error(f"matchday_run_failed: guild_id={guild_id}, error={e}\n{err_trace}")
            
            # Record failure in a separate database session so it doesn't get rolled back
            if job_key:
                try:
                    async with get_session() as fail_session:
                        await mark_job_failed(fail_session, job_key, f"{str(e)}\n{err_trace}")
                except Exception as e_job:
                    logger.error(f"Failed to record job failure: {e_job}")
                
            from app.error_reporting import capture_exception
            capture_exception(e)
            return MatchdayRunResult(
                success=False,
                code="database_error",
                message="A database error occurred during matchday simulation. All fixtures rolled back."
            )
