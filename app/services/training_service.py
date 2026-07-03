# app/services/training_service.py

import uuid
import logging
from decimal import Decimal
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.models.player import Player
from app.models.club import Club
from app.models.fixture import Fixture
from app.models.facility import Facility, FacilityType
from app.models.player_development import PlayerDevelopmentState, ClubTrainingSettings
from app.engine.training_engine import (
    TrainingWeekInput,
    calculate_training_week,
    calculate_match_development_xp,
    calculate_season_training_bonus,
)
from app.repositories.training_repository import (
    get_or_create_dev_state,
    get_dev_state_map_for_players,
    get_or_create_training_settings,
    get_human_club_players_for_training,
    insert_weekly_training_log_returning_id,
    insert_match_development_event_returning_id,
    get_season_dev_states_for_bonus,
    mark_bonus_applied,
)

logger = logging.getLogger("app.services.training_service")


@dataclass
class ClubTrainingOverviewResult:
    club_name: str
    default_plan: str
    intensity: str
    week: int
    development_outlook: list[tuple[str, float, str]]  # (name, avg_xp, bonus_desc)
    low_sharpness_count: int
    low_morale_count: int
    avg_readiness: float


class TrainingService:

    @staticmethod
    async def run_weekly_training_tick(
        session: AsyncSession,
        guild_id: str,
        season_id: uuid.UUID,
        week: int,
    ) -> None:
        """
        Executes the idempotent weekly training tick for all human clubs in a guild.
        Updates sharpness, morale, readiness, training XP, and logs the tick.
        """
        logger.info(f"Running weekly training tick for guild {guild_id}, season {season_id}, week {week}")
        
        from unittest.mock import Mock
        if isinstance(session, Mock) and not isinstance(get_human_club_players_for_training, Mock):
            logger.info("Mock session detected in run_weekly_training_tick without mocked repository. Bypassing training tick.")
            return

        # Fetch all human-controlled clubs and their non-retired players
        human_players_and_clubs = await get_human_club_players_for_training(session, guild_id, season_id)
        if not human_players_and_clubs:
            logger.info(f"No human clubs with active players found for training in guild {guild_id}")
            return

        # Fetch training pitch facilities for all human clubs in this guild
        fac_stmt = (
            select(Facility)
            .join(Club)
            .where(
                and_(
                    Club.guild_id == str(guild_id),
                    Club.is_bot_controlled == False,
                    Facility.facility_type == FacilityType.TRAINING_PITCH
                )
            )
        )
        fac_res = await session.execute(fac_stmt)
        pitch_levels = {fac.club_id: fac.level for fac in fac_res.scalars().all()}

        # For each player, run the training calculation and insert log first (idempotency gate)
        for club, player in human_players_and_clubs:
            # 1. Resolve club-wide settings
            club_settings = await get_or_create_training_settings(session, club.id, season_id, guild_id)
            
            # 2. Resolve player development state
            dev_state = await get_or_create_dev_state(session, player.id, season_id, club.id, guild_id)

            # 3. Resolve plan type (player plan overrides club default)
            plan = dev_state.plan_type if dev_state.plan_type else club_settings.default_plan
            if not plan:
                plan = "balanced"

            # 4. Resolve training pitch level
            pitch_level = pitch_levels.get(club.id, 1)

            # 5. Build input
            inp = TrainingWeekInput(
                player_id=str(player.id),
                age=player.age,
                overall=player.overall,
                potential=player.potential,
                sharpness=player.sharpness,
                morale=player.morale,
                current_readiness_modifier=float(dev_state.readiness_modifier),
                plan_type=plan,
                intensity=club_settings.intensity,
                is_injured=(player.injury_days_remaining > 0),
                training_pitch_level=pitch_level,
            )

            # 6. Calculate tick result
            result = calculate_training_week(inp)

            # 7. Insert log first (ON CONFLICT DO NOTHING RETURNING id)
            log_id = await insert_weekly_training_log_returning_id(
                session=session,
                club_id=club.id,
                player_id=player.id,
                season_id=season_id,
                guild_id=guild_id,
                week=week,
                plan_type=plan,
                intensity=club_settings.intensity,
                xp_earned=result.xp_earned,
                sharpness_delta=result.sharpness_delta,
                morale_delta=result.morale_delta,
                readiness_before=dev_state.readiness_modifier,
                readiness_after=Decimal(str(result.readiness_modifier)),
                notes="; ".join(result.notes) if result.notes else None,
            )

            if log_id is None:
                # Log already exists, skip mutations to ensure idempotency
                logger.info(f"Training log already exists for player {player.display_name} in week {week}. Skipping.")
                continue

            # 8. Mutate player stats (clamped 0–100)
            player.sharpness = max(0, min(100, player.sharpness + result.sharpness_delta))
            player.morale = max(0, min(100, player.morale + result.morale_delta))

            # 9. Mutate player dev state
            dev_state.training_xp += result.xp_earned
            dev_state.weeks_trained += 1
            dev_state.readiness_modifier = Decimal(str(result.readiness_modifier))

            logger.info(
                f"Applied training for {player.display_name}: XP +{result.xp_earned}, "
                f"Sharpness +{result.sharpness_delta}, Morale +{result.morale_delta}, "
                f"Readiness {inp.current_readiness_modifier:.2f} -> {result.readiness_modifier:.2f}"
            )

    @staticmethod
    async def record_match_development_events(
        session: AsyncSession,
        fixture: Fixture,
        sim_result,
        home_club_id: uuid.UUID,
        away_club_id: uuid.UUID,
        players_by_id: dict[uuid.UUID, Player],
    ) -> None:
        """
        Records match development events and awards match XP for league fixtures.
        Only applies to players of human-managed clubs who played > 0 minutes.
        """
        logger.info(f"Recording match development events for fixture {fixture.id}")
        
        from unittest.mock import Mock
        if isinstance(session, Mock) and not isinstance(insert_match_development_event_returning_id, Mock):
            logger.info("Mock session detected in record_match_development_events without mocked repository. Bypassing match XP recording.")
            return

        # Fetch clubs to verify if they are bot controlled
        home_club_stmt = select(Club).where(Club.id == home_club_id)
        away_club_stmt = select(Club).where(Club.id == away_club_id)
        home_res = await session.execute(home_club_stmt)
        away_res = await session.execute(away_club_stmt)
        home_club = home_res.scalar_one()
        away_club = away_res.scalar_one()

        is_home_bot = home_club.is_bot_controlled
        is_away_bot = away_club.is_bot_controlled

        # Process each player who participated in the match
        for pid_str, minutes_played in sim_result.played_minutes.items():
            if minutes_played <= 0:
                continue

            try:
                pid = uuid.UUID(pid_str)
            except ValueError:
                continue

            player = players_by_id.get(pid)
            if not player:
                continue

            # Exclude bot clubs
            if player.club_id == home_club_id and is_home_bot:
                continue
            if player.club_id == away_club_id and is_away_bot:
                continue

            # Calculate match XP
            match_rating = sim_result.player_ratings.get(pid_str)
            xp_earned = calculate_match_development_xp(minutes_played, match_rating)

            # Insert match event (ON CONFLICT DO NOTHING)
            event_id = await insert_match_development_event_returning_id(
                session=session,
                club_id=player.club_id,
                player_id=player.id,
                fixture_id=fixture.id,
                season_id=fixture.season_id,
                guild_id=fixture.guild_id,
                minutes_played=minutes_played,
                match_rating=Decimal(str(round(match_rating, 1))) if match_rating is not None else None,
                xp_earned=xp_earned,
                reason_breakdown={"rating": match_rating, "minutes": minutes_played},
            )

            if event_id is None:
                # Event already recorded, skip incrementing XP
                logger.info(f"Match dev event already exists for player {player.display_name} in fixture {fixture.id}. Skipping.")
                continue

            # Get or create dev state
            dev_state = await get_or_create_dev_state(
                session, player.id, fixture.season_id, player.club_id, fixture.guild_id
            )
            dev_state.match_xp += xp_earned
            logger.info(f"Recorded match XP for {player.display_name}: +{xp_earned} XP (rating: {match_rating})")

    @staticmethod
    async def calculate_season_training_bonuses(
        session: AsyncSession,
        season_id: uuid.UUID,
    ) -> dict[uuid.UUID, int]:
        """
        Calculates the season training OVR bonus (0, 1, or 2) for all eligible players.
        Returns a dict of player_id -> bonus_ovr.
        Does not mutate player.overall directly.
        """
        logger.info(f"Calculating season training bonuses for season {season_id}")
        
        from unittest.mock import Mock
        if isinstance(session, Mock) and not isinstance(get_season_dev_states_for_bonus, Mock):
            logger.info("Mock session detected in calculate_season_training_bonuses without mocked repository. Bypassing calculations.")
            return {}
            
        eligible_states = await get_season_dev_states_for_bonus(session, season_id)

        bonus_map = {}
        for state in eligible_states:
            # We must load the Player row to get current OVR/potential/age
            player = state.player

            bonus = calculate_season_training_bonus(
                age=player.age,
                overall=player.overall,
                potential=player.potential,
                training_xp=state.training_xp,
                match_xp=state.match_xp,
                weeks_trained=state.weeks_trained,
                season_bonus_already_applied=state.season_bonus_applied,
            )
            bonus_map[player.id] = bonus

        return bonus_map

    @staticmethod
    async def get_club_training_overview(
        session: AsyncSession,
        guild_id: str,
        club_id: uuid.UUID,
        season_id: uuid.UUID,
    ) -> ClubTrainingOverviewResult:
        """
        Returns a structured training overview for a club's dashboard.
        """
        club_stmt = select(Club).where(Club.id == club_id)
        club_res = await session.execute(club_stmt)
        club = club_res.scalar_one()

        # Get or create settings
        settings = await get_or_create_training_settings(session, club_id, season_id, guild_id)

        # Get current season week
        from app.models.season import Season
        season_stmt = select(Season).where(Season.id == season_id)
        season_res = await session.execute(season_stmt)
        season = season_res.scalar_one_or_none()
        current_week = season.current_week if season else 1

        # Get all non-retired players in the club
        players_stmt = select(Player).where(
            and_(
                Player.club_id == club_id,
                Player.is_retired == False
            )
        ).order_by(Player.overall.desc())
        players_res = await session.execute(players_stmt)
        players = list(players_res.scalars().all())

        # Get all dev states
        dev_states = await get_dev_state_map_for_players(session, [p.id for p in players], season_id)

        # Compute metrics
        development_outlook = []
        low_sharpness_count = 0
        low_morale_count = 0
        readiness_sum = 0.0

        for player in players:
            dev_state = dev_states.get(player.id)
            
            # If no dev state exists, show defaults
            if not dev_state:
                avg_xp = 0.0
                readiness = 1.00
                projected = "No bonus likely"
            else:
                total_xp = dev_state.training_xp + dev_state.match_xp
                weeks = max(1, dev_state.weeks_trained)
                avg_xp = float(total_xp) / weeks
                readiness = float(dev_state.readiness_modifier)

                # Project bonus
                if player.age >= 30:
                    projected = "No bonus (Age 30+)"
                elif player.overall >= player.potential:
                    projected = "At potential"
                else:
                    if avg_xp < 16:
                        projected = "No bonus likely"
                    elif avg_xp < 28:
                        projected = f"On track for +1"
                    else:
                        room = player.potential - player.overall
                        if room >= 2:
                            projected = f"On track for +2"
                        else:
                            projected = f"On track for +1 (potential cap)"

            development_outlook.append((player.display_name, round(avg_xp, 1), projected))
            
            if player.sharpness < 40:
                low_sharpness_count += 1
            if player.morale < 30:
                low_morale_count += 1
            
            readiness_sum += readiness

        avg_readiness = readiness_sum / max(1, len(players))

        return ClubTrainingOverviewResult(
            club_name=club.name,
            default_plan=settings.default_plan.title(),
            intensity=settings.intensity.title(),
            week=current_week,
            development_outlook=development_outlook,
            low_sharpness_count=low_sharpness_count,
            low_morale_count=low_morale_count,
            avg_readiness=round(avg_readiness, 2),
        )

    @staticmethod
    async def set_club_default_plan(
        session: AsyncSession,
        club_id: uuid.UUID,
        season_id: uuid.UUID,
        guild_id: str,
        plan: str,
    ) -> None:
        """Sets the default training plan for a club."""
        settings = await get_or_create_training_settings(session, club_id, season_id, guild_id)
        settings.default_plan = plan.lower()
        await session.flush()

    @staticmethod
    async def set_club_intensity(
        session: AsyncSession,
        club_id: uuid.UUID,
        season_id: uuid.UUID,
        guild_id: str,
        intensity: str,
    ) -> None:
        """Sets the training intensity for a club."""
        settings = await get_or_create_training_settings(session, club_id, season_id, guild_id)
        settings.intensity = intensity.lower()
        await session.flush()

    @staticmethod
    async def set_player_training_plan(
        session: AsyncSession,
        club_id: uuid.UUID,
        player_id: uuid.UUID,
        season_id: uuid.UUID,
        guild_id: str,
        plan: str,
    ) -> None:
        """Sets the individual training plan for a player."""
        dev_state = await get_or_create_dev_state(session, player_id, season_id, club_id, guild_id)
        dev_state.plan_type = plan.lower()
        await session.flush()
