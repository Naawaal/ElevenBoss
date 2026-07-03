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
from app.services.lineup_service import LineupService
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
from app.models.scheduler_run import SchedulerRun, SchedulerRunStatus

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
                    from datetime import timedelta, timezone
                    from sqlalchemy import update as sa_update
                    from app.repositories import STALE_MATCHDAY_LOCK_HOURS

                    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_MATCHDAY_LOCK_HOURS)

                    # Atomic conditional UPDATE — only one concurrent caller can win this.
                    # If both the startup sweep and this inline check race on the same stale
                    # lock, the one that executes the UPDATE first will get rowcount=1 and
                    # proceed; the second will get rowcount=0 and branch to the re-fetch below.
                    update_stmt = (
                        sa_update(SchedulerRun)
                        .where(
                            SchedulerRun.job_key == job_key,
                            SchedulerRun.status == SchedulerRunStatus.RUNNING,
                            SchedulerRun.started_at < stale_cutoff,
                        )
                        .values(
                            status=SchedulerRunStatus.FAILED,
                            finished_at=datetime.now(timezone.utc),
                            error="stale_lock_recovered_inline",
                        )
                        .execution_options(synchronize_session="fetch")
                    )
                    recovery_result = await session.execute(update_stmt)

                    if recovery_result.rowcount == 0:
                        # Zero rows updated: either the lock isn't stale yet,
                        # or the startup sweep already won the race.
                        # Re-fetch to distinguish.
                        current_job = await get_job_by_key(session, job_key)
                        if current_job and current_job.status == SchedulerRunStatus.RUNNING:
                            # Genuinely still in-progress (not stale) — reject as normal
                            logger.info(f"matchday_run_rejected: reason=job_in_progress, job_key={job_key}")
                            return MatchdayRunResult(
                                success=False,
                                code="matchday_in_progress",
                                message=f"Week {current_week} simulation is already in progress.",
                            )
                        # Sweep already recovered it to FAILED — fall through to fresh lock
                        logger.info(
                            f"matchday_stale_lock_already_recovered: job_key={job_key}, "
                            f"recovered_by=startup_sweep"
                        )
                    else:
                        # This caller won the race — lock flipped to FAILED, fall through
                        logger.warning(
                            f"matchday_stale_lock_recovered: job_key={job_key}, "
                            f"recovered_by=inline_check, "
                            f"started_at={existing_job.started_at}"
                        )
                    # Fall through — create_running_job below creates the fresh RUNNING lock

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

                # 2. Refresh lineups for all bot filler clubs in the league
                from app.engine.lineup_builder import build_auto_lineup

                all_clubs = await get_clubs_in_league(session, guild_id, league.id)
                bot_clubs = [c for c in all_clubs if c.is_bot_controlled]
                for bot_club in bot_clubs:
                    club_players = await get_players_by_club_id(session, bot_club.id)
                    starters_objs, bench_objs, _ = build_auto_lineup(club_players, "4-4-2")
                    starters_ids = {slot: p.id for slot, p in starters_objs.items()}
                    bench_ids = [p.id for p in bench_objs]
                    await save_lineup_with_players(
                        session,
                        guild_id,
                        bot_club.id,
                        "4-4-2",
                        starters_ids,
                        bench_ids
                    )
                await session.flush()
                logger.info(f"bot_lineups_refreshed: guild_id={guild_id}, count={len(bot_clubs)}")
                    
                results_list = []
                # Simulate each fixture
                for fixture in fixtures:
                    home_club = fixture.home_club
                    away_club = fixture.away_club

                    try:
                        home_res = await LineupService.resolve_team_lineup(session, guild_id, home_club.id, home_club.name, persist_fallback=True)
                        away_res = await LineupService.resolve_team_lineup(session, guild_id, away_club.id, away_club.name, persist_fallback=True)
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
                        formation=home_res.formation,
                        players=home_res.starters,
                        bench=home_res.bench,
                        is_home=True
                    )
                    away_team_input = MatchTeamInput(
                        club_id=str(away_club.id),
                        club_name=away_club.name,
                        formation=away_res.formation,
                        players=away_res.starters,
                        bench=away_res.bench,
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
                    # Substitutions
                    for s in sim_result.substitutions:
                        events_list.append(MatchEvent(
                            guild_id=str(guild_id),
                            fixture_id=fixture.id,
                            minute=s.minute,
                            event_type=MatchEventType.SUBSTITUTION,
                            club_id=uuid.UUID(s.club_id),
                            player_id=uuid.UUID(s.player_in_id),
                            secondary_player_id=uuid.UUID(s.player_out_id),
                            description=s.description
                        ))
                    # Injuries
                    for inj in sim_result.injuries:
                        events_list.append(MatchEvent(
                            guild_id=str(guild_id),
                            fixture_id=fixture.id,
                            minute=inj.minute,
                            event_type=MatchEventType.INJURY,
                            club_id=uuid.UUID(inj.club_id),
                            player_id=uuid.UUID(inj.player_id),
                            description=inj.description
                        ))
                    await bulk_create_match_events(session, events_list)
                    logger.info(f"match_events_saved: fixture_id={fixture.id}, count={len(events_list)}")
                    
                    # Apply persistent match consequences (fitness decay, red cards, injuries)
                    from app.services.match_consequence_service import MatchConsequenceService
                    await MatchConsequenceService.apply_league_match_consequences(
                        session=session,
                        fixture_id=fixture.id,
                        sim_result=sim_result,
                        home_club_id=home_club.id,
                        away_club_id=away_club.id
                    )
                    
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
                     from app.services.league_lifecycle_service import LeagueLifecycleService
                     await LeagueLifecycleService.complete_current_season(session, guild_id, season.id)
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
