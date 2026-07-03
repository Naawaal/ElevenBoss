import logging
import uuid
import random
import hashlib
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.club import Club
from app.models.player import Player
from app.repositories import get_players_by_club_id, get_active_lineup
from app.engine.lineup_builder import build_auto_lineup
from app.engine.lineup_validator import validate_lineup
from app.services.lineup_service import LineupService
from app.engine.match_engine import (
    simulate_match,
    MatchPlayerInput,
    MatchTeamInput,
    MatchSimulationInput,
    MatchSimulationResult,
)

logger = logging.getLogger("app.services.friendly_service")

# Simple pool of names for transient bot player generation
BOT_FIRST_NAMES = [
    "Adam", "Alex", "Ben", "Chris", "Daniel", "David", "Eric", "Frank", "George", "Henry",
    "Jack", "John", "Kevin", "Leo", "Luke", "Mark", "Matt", "Oliver", "Paul", "Ryan",
    "Sam", "Tom", "Will", "Zach", "Aaron", "Blake", "Cole", "Dylan", "Ethan", "Felix"
]
BOT_LAST_NAMES = [
    "Smith", "Jones", "Brown", "Taylor", "Wilson", "Miller", "Davis", "White", "Clark", "Hall",
    "Thomas", "Martin", "Baker", "Carter", "Evans", "Green", "Hill", "King", "Lee", "Morris",
    "Nelson", "Parker", "Reed", "Scott", "Turner", "Ward", "Young", "Bell", "Cook", "Gray"
]

@dataclass
class FriendlyMatchReport:
    home_club_id: str
    away_club_id: str
    home_club_name: str
    away_club_name: str
    home_goals: int
    away_goals: int
    home_possession: int
    away_possession: int
    home_shots: int
    away_shots: int
    home_shots_on_target: int
    away_shots_on_target: int
    motm_player_name: str
    timeline: list[dict] = field(default_factory=list) # Elements have: minute, type, description, club_id


class FriendlyService:

    @staticmethod
    async def get_cooldown_expiry(session: AsyncSession, guild_id: int | str, challenger_id: int | str, opponent_id: int | str) -> datetime | None:
        """
        Gets cooldown expiry time if the challenger is on cooldown against the opponent.
        """
        from app.repositories.friendly_repository import get_friendly_cooldown
        cooldown = await get_friendly_cooldown(session, guild_id, challenger_id, opponent_id)
        if cooldown:
            return cooldown.expires_at
        return None

    @staticmethod
    async def set_cooldown(session: AsyncSession, guild_id: int | str, challenger_id: int | str, opponent_id: int | str, duration_minutes: int = 5):
        """
        Sets a friendly match challenge cooldown.
        """
        from app.repositories.friendly_repository import set_friendly_cooldown
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        await set_friendly_cooldown(session, guild_id, challenger_id, opponent_id, expires_at)

    @staticmethod
    def generate_transient_bot_team(difficulty_level: str, club_name: str, seed: int) -> MatchTeamInput:
        """
        Generates a pure in-memory MatchTeamInput for a virtual practice bot club.
        Difficulty Levels:
        - beginner: 50-59 overall
        - amateur: 60-69 overall
        - professional: 70-79 overall
        - world_class: 80-89 overall
        - legend: 90-95 overall
        """
        rng = random.Random(seed)
        
        # Determine rating range
        diff_str = difficulty_level.lower()
        if diff_str == "beginner":
            min_ovr, max_ovr = 50, 59
        elif diff_str == "amateur":
            min_ovr, max_ovr = 60, 69
        elif diff_str == "professional":
            min_ovr, max_ovr = 70, 79
        elif diff_str == "world_class":
            min_ovr, max_ovr = 80, 89
        elif diff_str == "legend":
            min_ovr, max_ovr = 90, 95
        else:
            min_ovr, max_ovr = 65, 75 # Default to professional/amateur mix
            
        # 4-4-2 layout slots & position mappings
        slots = {
            "GK": "GK",
            "LB": "LB",
            "CB1": "CB",
            "CB2": "CB",
            "RB": "RB",
            "LM": "LM",
            "CM1": "CM",
            "CM2": "CM",
            "RM": "RM",
            "ST1": "ST",
            "ST2": "ST",
        }
        
        players = []
        for slot, pos in slots.items():
            first = rng.choice(BOT_FIRST_NAMES)
            last = rng.choice(BOT_LAST_NAMES)
            name = f"{first} {last}"
            ovr = rng.randint(min_ovr, max_ovr)
            
            players.append(MatchPlayerInput(
                player_id=str(uuid.uuid4()),
                name=name,
                position=pos,
                slot=slot,
                overall=ovr,
                potential=ovr + rng.randint(0, 5),
                fitness=100,
                morale=80,
                consistency=75,
                is_goalkeeper=(pos == "GK")
            ))
            
        return MatchTeamInput(
            club_id=str(uuid.uuid4()),
            club_name=club_name,
            formation="4-4-2",
            players=players,
            is_home=False
        )

    @staticmethod
    def simulate_friendly(
        home_team: MatchTeamInput,
        away_team: MatchTeamInput,
        seed: int
    ) -> FriendlyMatchReport:
        """
        Runs the match engine in-memory and returns a FriendlyMatchReport DTO.
        """
        sim_input = MatchSimulationInput(
            fixture_id=str(uuid.uuid4()),
            week=1,
            home_team=home_team,
            away_team=away_team,
            seed=seed,
            home_tactic="balanced",
            away_tactic="balanced"
        )
        
        logger.info(f"friendly_simulation_started: seed={seed}, home={home_team.club_name}, away={away_team.club_name}")
        result: MatchSimulationResult = simulate_match(sim_input)
        logger.info(f"friendly_simulated: home={home_team.club_name}, away={away_team.club_name}, score={result.home_goals}-{result.away_goals}")
        
        # Find MOTM name from players list
        motm_name = "Unknown Player"
        all_players = home_team.players + away_team.players
        if result.motm_player_id:
            for p in all_players:
                if p.player_id == result.motm_player_id:
                    motm_name = p.name
                    break
                    
        # Map timeline events to list of dict
        timeline_events = []
        for event in result.timeline_events:
            timeline_events.append({
                "minute": event.get("minute", 0),
                "type": event.get("type", "generic"),
                "description": event.get("description", ""),
                "club_id": str(event.get("club_id", "")) if event.get("club_id") else None
            })
            
        return FriendlyMatchReport(
            home_club_id=str(home_team.club_id),
            away_club_id=str(away_team.club_id),
            home_club_name=home_team.club_name,
            away_club_name=away_team.club_name,
            home_goals=result.home_goals,
            away_goals=result.away_goals,
            home_possession=result.home_possession,
            away_possession=result.away_possession,
            home_shots=result.home_shots,
            away_shots=result.away_shots,
            home_shots_on_target=result.home_shots_on_target,
            away_shots_on_target=result.away_shots_on_target,
            motm_player_name=motm_name,
            timeline=timeline_events
        )
