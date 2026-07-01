# app/engine/match_engine.py

import math
import random
from dataclasses import dataclass, field
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

def simulate_match(input_data: MatchSimulationInput) -> MatchSimulationResult:
    """
    Simulate a match between home and away team deterministically using local rng.
    """
    rng = random.Random(input_data.seed)
    
    home_strength = calculate_team_strength(input_data.home_team.formation, input_data.home_team.players, is_home=True)
    away_strength = calculate_team_strength(input_data.away_team.formation, input_data.away_team.players, is_home=False)
    
    # 1. Expected Goals (xG)
    # Delta of Attack vs Defense, plus Midfield influence, plus home advantage
    home_advantage = 0.2
    home_xg = 1.3 + (home_strength.attack - away_strength.defense) * 0.05 + (home_strength.midfield - away_strength.midfield) * 0.03 + home_advantage
    away_xg = 1.3 + (away_strength.attack - home_strength.defense) * 0.05 + (away_strength.midfield - home_strength.midfield) * 0.03
    
    home_xg = max(0.2, min(4.0, home_xg))
    away_xg = max(0.2, min(4.0, away_xg))
    
    # Generate actual goals using Poisson distribution
    home_goals = _poisson_sample(rng, home_xg)
    away_goals = _poisson_sample(rng, away_xg)
    
    # 2. Match Statistics
    # Possession based on midfield strength delta
    pos_delta = (home_strength.midfield - away_strength.midfield) * 0.4
    home_possession = int(50 + pos_delta)
    home_possession = max(35, min(65, home_possession))
    away_possession = 100 - home_possession
    
    # Shots based on attack vs defense delta
    home_shots = int(rng.randint(6, 18) + (home_strength.attack - away_strength.defense) * 0.2)
    away_shots = int(rng.randint(6, 18) + (away_strength.attack - home_strength.defense) * 0.2)
    home_shots = max(3, min(30, home_shots))
    away_shots = max(3, min(30, away_shots))
    
    # Shots on target
    home_sot = int(home_shots * rng.uniform(0.25, 0.55))
    away_sot = int(away_shots * rng.uniform(0.25, 0.55))
    
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
    goals_list = []
    
    def attribute_goal(team: MatchTeamInput, opponent: MatchTeamInput, minute: int) -> MatchGoalEvent:
        # Determine scorer weights based on slot
        scorer_candidates = []
        scorer_weights = []
        for p in team.players:
            slot = p.slot.upper()
            if slot.startswith("ST") or slot.startswith("CF"):
                w = 100
            elif slot in ("LW", "RW"):
                w = 80
            elif slot in ("CAM",):
                w = 60
            elif slot in ("LM", "RM", "CM1", "CM2", "CM3"):
                w = 30
            elif slot in ("LDM", "RDM"):
                w = 15
            elif slot == "GK":
                w = 0.01
            else:
                w = 5  # defender slots
            scorer_candidates.append(p)
            scorer_weights.append(w)
            
        scorer = rng.choices(scorer_candidates, weights=scorer_weights, k=1)[0]
        
        # Determine assist (70% chance)
        assist = None
        if rng.random() < 0.70 and len(team.players) > 1:
            assist_candidates = []
            assist_weights = []
            for p in team.players:
                if p.player_id == scorer.player_id:
                    continue
                slot = p.slot.upper()
                if slot in ("CAM", "LM", "RM", "CM1", "CM2", "CM3", "LDM", "RDM"):
                    w = 100
                elif slot.startswith("ST") or slot in ("LW", "RW"):
                    w = 60
                elif slot == "GK":
                    w = 1
                else:
                    w = 30  # defenders
                assist_candidates.append(p)
                assist_weights.append(w)
            if assist_candidates:
                assist = rng.choices(assist_candidates, weights=assist_weights, k=1)[0]
                
        desc = f"Goal! {scorer.name} scores for {team.club_name}."
        if assist:
            desc += f" Assisted by {assist.name}."
            
        return MatchGoalEvent(
            minute=minute,
            club_id=team.club_id,
            scorer_id=scorer.player_id,
            assist_id=assist.player_id if assist else None,
            description=desc
        )

    # Distribute goal minutes randomly between 1 and 90
    home_goal_minutes = sorted([rng.randint(1, 90) for _ in range(home_goals)])
    away_goal_minutes = sorted([rng.randint(1, 90) for _ in range(away_goals)])
    
    for m in home_goal_minutes:
        goals_list.append(attribute_goal(input_data.home_team, input_data.away_team, m))
    for m in away_goal_minutes:
        goals_list.append(attribute_goal(input_data.away_team, input_data.home_team, m))
        
    # 4. Generate Cards (Yellow / Red)
    cards_list = []
    
    def process_cards(team: MatchTeamInput):
        # Tracking yellow cards to handle double yellow -> red
        yellow_counts = {}
        for p in team.players:
            if p.slot.upper() == "GK":
                card_prob = 0.02
            elif p.slot.upper() in ("LB", "CB1", "CB2", "CB3", "RB", "LWB", "RWB", "LDM", "RDM"):
                card_prob = 0.15
            else:
                card_prob = 0.08
                
            # Roll for yellow
            if rng.random() < card_prob:
                minute = rng.randint(1, 90)
                desc = f"Yellow card shown to {p.name} ({team.club_name}) for a tactical foul."
                cards_list.append(MatchCardEvent(
                    minute=minute,
                    club_id=team.club_id,
                    player_id=p.player_id,
                    card_type="yellow",
                    description=desc
                ))
                yellow_counts[p.player_id] = yellow_counts.get(p.player_id, 0) + 1
                
                # Check for double yellow
                if yellow_counts[p.player_id] == 2:
                    red_min = min(90, minute + rng.randint(1, 10))
                    desc_red = f"Red card! {p.name} ({team.club_name}) is sent off after receiving a second yellow card."
                    cards_list.append(MatchCardEvent(
                        minute=red_min,
                        club_id=team.club_id,
                        player_id=p.player_id,
                        card_type="red",
                        description=desc_red
                    ))
            # Roll for direct red (extremely rare: 0.5% chance)
            elif rng.random() < 0.005:
                minute = rng.randint(1, 90)
                desc = f"Red card! {p.name} ({team.club_name}) is sent off for a dangerous tackle."
                cards_list.append(MatchCardEvent(
                    minute=minute,
                    club_id=team.club_id,
                    player_id=p.player_id,
                    card_type="red",
                    description=desc
                ))
                
    process_cards(input_data.home_team)
    process_cards(input_data.away_team)
    
    # Sort goals & cards to build timeline events
    timeline = []
    
    # Add match start event
    timeline.append({
        "minute": 0,
        "type": "match_start",
        "description": f"The referee blows the whistle and the match between {input_data.home_team.club_name} and {input_data.away_team.club_name} begins!"
    })
    
    # Sort other events by minute
    all_game_events = []
    for g in goals_list:
        all_game_events.append((g.minute, "goal", g))
    for c in cards_list:
        all_game_events.append((c.minute, c.card_type, c))
        
    all_game_events.sort(key=lambda x: x[0])
    
    halftime_inserted = False
    for minute, etype, obj in all_game_events:
        # Insert half-time at minute 45
        if minute > 45 and not halftime_inserted:
            timeline.append({
                "minute": 45,
                "type": "half_time",
                "description": f"Half-Time: {input_data.home_team.club_name} {home_goals}–{away_goals} {input_data.away_team.club_name}."
            })
            halftime_inserted = True
            
        timeline.append({
            "minute": minute,
            "type": etype,
            "description": obj.description,
            "club_id": obj.club_id,
            "player_id": obj.player_id if etype in ("yellow", "red") else getattr(obj, "scorer_id", None),
            "secondary_player_id": getattr(obj, "assist_id", None)
        })
        
    if not halftime_inserted:
        timeline.append({
            "minute": 45,
            "type": "half_time",
            "description": f"Half-Time: {input_data.home_team.club_name} {home_goals}–{away_goals} {input_data.away_team.club_name}."
        })
        
    # Add full time event
    timeline.append({
        "minute": 90,
        "type": "full_time",
        "description": f"Full-Time: The referee blows the final whistle. Final score is {input_data.home_team.club_name} {home_goals}–{away_goals} {input_data.away_team.club_name}."
    })
    
    # 5. Player Ratings
    player_ratings = {}
    
    def calculate_ratings(team: MatchTeamInput, goals_scored: int, goals_conceded: int, won: bool, drew: bool):
        for p in team.players:
            # Base rating
            base = rng.uniform(6.0, 7.0)
            
            # Scorer / Assist bonuses
            goals_count = sum(1 for g in goals_list if g.club_id == team.club_id and g.scorer_id == p.player_id)
            assists_count = sum(1 for g in goals_list if g.club_id == team.club_id and g.assist_id == p.player_id)
            
            base += goals_count * 1.5
            base += assists_count * 0.8
            
            # Conceded penalty for GKs and defenders
            is_def_or_gk = p.slot.upper() == "GK" or p.slot.upper() in ("LB", "CB1", "CB2", "CB3", "RB", "LWB", "RWB")
            if is_def_or_gk:
                if goals_conceded == 0:
                    base += 1.0  # Clean sheet bonus
                else:
                    base -= goals_conceded * 0.25
                    
            # Card penalties
            has_yellow = any(c.player_id == p.player_id and c.card_type == "yellow" for c in cards_list)
            has_red = any(c.player_id == p.player_id and c.card_type == "red" for c in cards_list)
            
            if has_yellow:
                base -= 0.5
            if has_red:
                base -= 1.5
                
            # Result modifiers
            if won:
                base += 0.5
            elif drew:
                base += 0.1
            else:
                base -= 0.5
                
            # Clamp to [3.0, 10.0]
            player_ratings[p.player_id] = round(max(3.0, min(10.0, base)), 1)
            
    home_won = home_goals > away_goals
    away_won = away_goals > home_goals
    drew = home_goals == away_goals
    
    calculate_ratings(input_data.home_team, home_goals, away_goals, home_won, drew)
    calculate_ratings(input_data.away_team, away_goals, home_goals, away_won, drew)
    
    # 6. MOTM (highest rating, break ties using overall or random)
    motm_player_id = None
    all_players = input_data.home_team.players + input_data.away_team.players
    best_rating = -1.0
    candidates = []
    
    for p in all_players:
        rating = player_ratings.get(p.player_id, 6.0)
        if rating > best_rating:
            best_rating = rating
            candidates = [p]
        elif rating == best_rating:
            candidates.append(p)
            
    if candidates:
        # Prefer player from the winning team
        winner_club_id = input_data.home_team.club_id if home_won else (input_data.away_team.club_id if away_won else None)
        winning_candidates = [c for c in candidates if c.slot in [p.slot for p in (input_data.home_team.players if winner_club_id == input_data.home_team.club_id else input_data.away_team.players)]]
        
        selected_motm = rng.choice(winning_candidates if winning_candidates else candidates)
        motm_player_id = selected_motm.player_id
        
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
