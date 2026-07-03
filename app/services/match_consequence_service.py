# app/services/match_consequence_service.py

import logging
import uuid
import random
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.player import Player
from app.models.fixture import Fixture

logger = logging.getLogger("app.services.match_consequence_service")

# --- Constants for Match Consequences ---
LEAGUE_RED_CARD_SUSPENSION_GAMES = 1

INJURY_SEVERITY_WEIGHTS = {
    "minor_knock": 55,
    "strain": 30,
    "sprain": 12,
    "serious": 3,
}

INJURY_DURATION_DAYS = {
    "minor_knock": (1, 2),
    "strain": (2, 4),
    "sprain": (4, 7),
    "serious": (8, 14),
}

INJURY_FITNESS_PENALTY = {
    "minor_knock": (8, 15),
    "strain": (15, 25),
    "sprain": (20, 35),
    "serious": (35, 50),
}

class MatchConsequenceService:
    @staticmethod
    async def apply_league_match_consequences(
        session: AsyncSession,
        fixture_id: uuid.UUID,
        sim_result,
        home_club_id: uuid.UUID,
        away_club_id: uuid.UUID,
    ) -> None:
        """
        Applies long-term consequences (fitness decay, injuries, and suspensions)
        to players after a competitive league fixture.
        
        This service is fully idempotent; if consequences were already applied, it skips.
        """
        # Fetch the Fixture and check consequences_applied_at
        stmt = select(Fixture).where(Fixture.id == fixture_id)
        res = await session.execute(stmt)
        fixture = res.scalar_one_or_none()
        if not fixture:
            logger.error(f"Fixture {fixture_id} not found when applying consequences.")
            return

        if fixture.consequences_applied_at is not None:
            logger.info(f"Consequences already applied for fixture {fixture_id}. Skipping.")
            return

        logger.info(f"Applying league match consequences for fixture {fixture_id}")

        # Query all non-retired players in both clubs
        players_stmt = select(Player).where(
            Player.club_id.in_([home_club_id, away_club_id]),
            Player.is_retired == False
        )
        players_res = await session.execute(players_stmt)
        players = list(players_res.scalars().all())
        players_by_id = {p.id: p for p in players}

        # Step 1: Decrement existing suspensions for players already suspended before this fixture
        for p in players:
            games_rem = p.suspension_games_remaining or 0
            if games_rem > 0:
                p.suspension_games_remaining = max(0, games_rem - 1)
                logger.info(f"Player {p.display_name} served 1 match suspension. Remaining: {p.suspension_games_remaining}")

        # Seed the local RNG for deterministic consequences (e.g. injury severity)
        rng = random.Random(fixture_id.int)

        # Step 2 & 3: Process fitness and minutes played
        for pid_str, final_fit_val in sim_result.final_fitness.items():
            try:
                pid = uuid.UUID(pid_str)
            except ValueError:
                continue
            
            p = players_by_id.get(pid)
            if not p:
                continue

            minutes_played = sim_result.played_minutes.get(pid_str, 0)
            p.last_match_minutes = minutes_played
            
            if minutes_played > 0:
                # Update fitness for starters and subbed-in players
                p.fitness = max(0, min(100, int(final_fit_val * 100)))
                # Update match rating
                rating_val = sim_result.player_ratings.get(pid_str)
                if rating_val is not None:
                    p.last_match_rating = Decimal(str(round(rating_val, 1)))
                logger.info(f"Updated match stats for {p.display_name}: mins={minutes_played}, fit={p.fitness}, rating={p.last_match_rating}")
            else:
                p.last_match_rating = None

        # Step 4: Apply new suspensions for red cards
        for card in sim_result.cards:
            if card.card_type == "red":
                try:
                    pid = uuid.UUID(card.player_id)
                except ValueError:
                    continue
                p = players_by_id.get(pid)
                if p:
                    p.suspension_games_remaining = LEAGUE_RED_CARD_SUSPENSION_GAMES
                    p.suspension_created_fixture_id = fixture_id
                    logger.info(f"Suspension applied to {p.display_name} for red card in fixture {fixture_id}")

        # Step 5: Apply new injuries
        for inj in sim_result.injuries:
            try:
                pid = uuid.UUID(inj.player_id)
            except ValueError:
                continue
            p = players_by_id.get(pid)
            if p:
                severity = rng.choices(
                    population=["minor_knock", "strain", "sprain", "serious"],
                    weights=[
                        INJURY_SEVERITY_WEIGHTS["minor_knock"],
                        INJURY_SEVERITY_WEIGHTS["strain"],
                        INJURY_SEVERITY_WEIGHTS["sprain"],
                        INJURY_SEVERITY_WEIGHTS["serious"]
                    ],
                    k=1
                )[0]
                
                min_days, max_days = INJURY_DURATION_DAYS[severity]
                days = rng.randint(min_days, max_days)
                
                min_fit, max_fit = INJURY_FITNESS_PENALTY[severity]
                fit_penalty = rng.randint(min_fit, max_fit)
                
                p.injury_type = severity.replace('_', ' ').title()
                p.injury_severity = severity
                p.injury_days_remaining = days
                p.injury_created_at = datetime.utcnow()
                p.fitness = max(0, p.fitness - fit_penalty)
                
                logger.info(f"Injury applied to {p.display_name}: {p.injury_type} ({days} days), fitness penalty={fit_penalty}")

        # Mark fixture consequences as applied
        fixture.consequences_applied_at = datetime.utcnow()
        
        # Step 6: Record match development XP (league path only; friendlies never reach here)
        from app.services.training_service import TrainingService
        await TrainingService.record_match_development_events(
            session=session,
            fixture=fixture,
            sim_result=sim_result,
            home_club_id=home_club_id,
            away_club_id=away_club_id,
            players_by_id=players_by_id,
        )
        
        await session.flush()
