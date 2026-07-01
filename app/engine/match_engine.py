# app/engine/match_engine.py

import math
import random
from dataclasses import dataclass, field
from app.engine.match_config import MatchEngineConfig
from app.engine.team_strength import calculate_team_strength, TeamStrength

@dataclass(frozen=True)
class MatchPlayerInput:
    player_id: str
    name: str
    position: str
    slot: str
    overall: int
    potential: int
    fitness: int
    morale: int | None = None
    is_goalkeeper: bool = False

@dataclass(frozen=True)
class MatchTeamInput:
    club_id: str
    club_name: str
    formation: str
    players: list[MatchPlayerInput]
    is_home: bool = False

@dataclass(frozen=True)
class MatchSimulationInput:
    fixture_id: str
    week: int
    home_team: MatchTeamInput
    away_team: MatchTeamInput
    seed: int

@dataclass(frozen=True)
class MatchGoalEvent:
    minute: int
    club_id: str
    scorer_id: str
    assist_id: str | None
    description: str

@dataclass(frozen=True)
class MatchCardEvent:
    minute: int
    club_id: str
    player_id: str
    card_type: str  # "yellow" or "red"
    description: str

@dataclass(frozen=True)
class MatchSimulationResult:
    home_goals: int
    away_goals: int
    home_possession: int
    away_possession: int
    home_shots: int
    away_shots: int
    home_shots_on_target: int
    away_shots_on_target: int
    goals: list[MatchGoalEvent] = field(default_factory=list)
    cards: list[MatchCardEvent] = field(default_factory=list)
    motm_player_id: str | None = None
    player_ratings: dict[str, float] = field(default_factory=dict)
    timeline_events: list = field(default_factory=list)

def _poisson_sample(rng: random.Random, L: float) -> int:
    """
    Standard Poisson sampler using a local Random generator.
    """
    k = 0
    p = 1.0
    limit = math.exp(-L)
    while p > limit:
        k += 1
        p *= rng.random()
    return k - 1

def simulate_match(
    input_data: MatchSimulationInput,
    config: MatchEngineConfig | None = None
) -> MatchSimulationResult:
    """
    Simulate a match between home and away team deterministically using local rng.
    """
    if config is None:
        config = MatchEngineConfig()
        
    rng = random.Random(input_data.seed)
    
    # Calculate team strengths using modular config values
    home_strength = calculate_team_strength(
        input_data.home_team.formation,
        input_data.home_team.players,
        is_home=True,
        config=config
    )
    away_strength = calculate_team_strength(
        input_data.away_team.formation,
        input_data.away_team.players,
        is_home=False,
        config=config
    )
    
    # 1. Expected Goals (xG)
    # Delta of Attack vs Defense, plus Midfield influence, plus home advantage
    home_xg = config.base_xg + (home_strength.attack - away_strength.defense) * 0.05 + (home_strength.midfield - away_strength.midfield) * 0.03 + config.home_advantage_xg
    away_xg = config.base_xg + (away_strength.attack - home_strength.defense) * 0.05 + (away_strength.midfield - home_strength.midfield) * 0.03
    
    home_xg = max(config.min_xg, min(config.max_xg, home_xg))
    away_xg = max(config.min_xg, min(config.max_xg, away_xg))
    
    # Generate actual goals using Poisson distribution
    home_goals = _poisson_sample(rng, home_xg)
    away_goals = _poisson_sample(rng, away_xg)
    
    # 2. Match Statistics
    # Possession based on midfield strength delta
    pos_delta = (home_strength.midfield - away_strength.midfield) * config.possession_delta_multiplier
    home_possession = int(50 + pos_delta)
    home_possession = max(config.min_possession, min(config.max_possession, home_possession))
    away_possession = 100 - home_possession
    
    # Shots based on attack vs defense delta
    home_shots = int(rng.randint(config.base_shots_min, config.base_shots_max) + (home_strength.attack - away_strength.defense) * config.shots_strength_multiplier)
    away_shots = int(rng.randint(config.base_shots_min, config.base_shots_max) + (away_strength.attack - home_strength.defense) * config.shots_strength_multiplier)
    home_shots = max(config.min_shots, min(config.max_shots, home_shots))
    away_shots = max(config.min_shots, min(config.max_shots, away_shots))
    
    # Shots on target
    home_sot = int(home_shots * rng.uniform(config.sot_ratio_min, config.sot_ratio_max))
    away_sot = int(away_shots * rng.uniform(config.sot_ratio_min, config.sot_ratio_max))
    
    # Logical safeguards:
    # shots_on_target cannot exceed shots, goals cannot exceed shots_on_target
    if home_sot < home_goals:
        home_sot = home_goals
    if home_shots < home_sot:
        home_shots = home_sot
        
    if away_sot < away_goals:
        away_sot = away_goals
    if away_shots < away_sot:
        away_shots = away_sot
        
    # 3. Generate Goal Events
    from app.engine.match_event_generator import generate_goal_events, generate_card_events, build_timeline
    
    home_goals_events = generate_goal_events(rng, input_data.home_team, input_data.away_team, home_goals, config)
    away_goals_events = generate_goal_events(rng, input_data.away_team, input_data.home_team, away_goals, config)
    goals_list = home_goals_events + away_goals_events
    
    # 4. Generate Cards (Yellow / Red)
    home_cards = generate_card_events(rng, input_data.home_team, config)
    away_cards = generate_card_events(rng, input_data.away_team, config)
    cards_list = home_cards + away_cards
    
    # Build timeline
    timeline = build_timeline(
        input_data.home_team,
        input_data.away_team,
        home_goals,
        away_goals,
        goals_list,
        cards_list
    )
    
    # 5. Player Ratings
    from app.engine.match_rating import calculate_player_ratings, select_motm
    
    player_ratings = calculate_player_ratings(
        rng,
        input_data.home_team,
        input_data.away_team,
        home_goals,
        away_goals,
        goals_list,
        cards_list,
        config
    )
    
    # 6. MOTM Selection
    home_won = home_goals > away_goals
    away_won = away_goals > home_goals
    motm_player_id = select_motm(
        rng,
        input_data.home_team,
        input_data.away_team,
        player_ratings,
        home_won,
        away_won
    )
    
    return MatchSimulationResult(
        home_goals=home_goals,
        away_goals=away_goals,
        home_possession=home_possession,
        away_possession=away_possession,
        home_shots=home_shots,
        away_shots=away_shots,
        home_shots_on_target=home_sot,
        away_shots_on_target=away_sot,
        goals=goals_list,
        cards=cards_list,
        motm_player_id=motm_player_id,
        player_ratings=player_ratings,
        timeline_events=timeline
    )
