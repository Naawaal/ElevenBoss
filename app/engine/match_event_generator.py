# app/engine/match_event_generator.py

import random
from app.engine.match_config import MatchEngineConfig
from app.engine.match_engine import (
    MatchTeamInput,
    MatchGoalEvent,
    MatchCardEvent,
)

def attribute_goal(
    rng: random.Random,
    team: MatchTeamInput,
    opponent: MatchTeamInput,
    minute: int,
    config: MatchEngineConfig,
) -> MatchGoalEvent:
    """
    Selects a scorer and an assist provider for a team's goal using configuration weights.
    """
    scorer_candidates = []
    scorer_weights = []
    for p in team.players:
        slot = p.slot.upper()
        # Find weight key
        if slot.startswith("ST") or slot.startswith("CF"):
            w = config.scorer_weights.get("ST", 100.0)
        elif slot in ("LW", "RW"):
            w = config.scorer_weights.get("LW", 80.0)
        elif slot in ("CAM",):
            w = config.scorer_weights.get("CAM", 60.0)
        elif slot in ("LM", "RM") or slot.startswith("CM"):
            w = config.scorer_weights.get("LM", 30.0)
        elif slot in ("LDM", "RDM", "CDM"):
            w = config.scorer_weights.get("LDM", 15.0)
        elif slot == "GK":
            w = config.scorer_weights.get("GK", 0.01)
        else:
            w = config.scorer_weights.get("DEFENDER", 5.0)
        scorer_candidates.append(p)
        scorer_weights.append(w)
        
    scorer = rng.choices(scorer_candidates, weights=scorer_weights, k=1)[0]
    
    # Determine assist
    assist = None
    if rng.random() < config.assist_probability and len(team.players) > 1:
        assist_candidates = []
        assist_weights = []
        for p in team.players:
            if p.player_id == scorer.player_id:
                continue
            slot = p.slot.upper()
            if slot in ("CAM", "LM", "RM", "CM1", "CM2", "CM3", "LDM", "RDM", "CDM"):
                w = config.assist_weights.get("CAM", 100.0)
            elif slot.startswith("ST") or slot in ("LW", "RW") or slot.startswith("CF"):
                w = config.assist_weights.get("ST", 60.0)
            elif slot == "GK":
                w = config.assist_weights.get("GK", 1.0)
            else:
                w = config.assist_weights.get("DEFENDER", 30.0)
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

def generate_goal_events(
    rng: random.Random,
    team: MatchTeamInput,
    opponent: MatchTeamInput,
    goals_count: int,
    config: MatchEngineConfig,
) -> list[MatchGoalEvent]:
    """
    Generates a list of goal events for a team distributed throughout the 90 minutes.
    """
    minutes = sorted([rng.randint(1, 90) for _ in range(goals_count)])
    events = []
    for m in minutes:
        events.append(attribute_goal(rng, team, opponent, m, config))
    return events

def generate_card_events(
    rng: random.Random,
    team: MatchTeamInput,
    config: MatchEngineConfig,
) -> list[MatchCardEvent]:
    """
    Generates card events for a team using configured rates and probabilities.
    """
    cards_list = []
    yellow_counts = {}
    
    for p in team.players:
        slot = p.slot.upper()
        if slot == "GK":
            card_prob = config.gk_yellow_prob
        elif slot in ("LB", "CB1", "CB2", "CB3", "RB", "LWB", "RWB", "LDM", "RDM", "CDM"):
            card_prob = config.def_dm_yellow_prob
        else:
            card_prob = config.other_yellow_prob
            
        # Roll for yellow card
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
            
            # Double yellow -> red card
            if yellow_counts[p.player_id] == 2:
                red_min = min(90, minute + rng.randint(config.double_yellow_min_gap, config.double_yellow_max_gap))
                desc_red = f"Red card! {p.name} ({team.club_name}) is sent off after receiving a second yellow card."
                cards_list.append(MatchCardEvent(
                    minute=red_min,
                    club_id=team.club_id,
                    player_id=p.player_id,
                    card_type="red",
                    description=desc_red
                ))
                
        # Direct red card roll
        elif rng.random() < config.direct_red_prob:
            minute = rng.randint(1, 90)
            desc = f"Red card! {p.name} ({team.club_name}) is sent off for a dangerous tackle."
            cards_list.append(MatchCardEvent(
                minute=minute,
                club_id=team.club_id,
                player_id=p.player_id,
                card_type="red",
                description=desc
            ))
            
    return cards_list

def build_timeline(
    home_team: MatchTeamInput,
    away_team: MatchTeamInput,
    home_goals: int,
    away_goals: int,
    goals: list[MatchGoalEvent],
    cards: list[MatchCardEvent],
) -> list[dict]:
    """
    Builds the chronological timeline event list for display.
    """
    timeline = []
    
    # 1. Match Start
    timeline.append({
        "minute": 0,
        "type": "match_start",
        "description": f"The referee blows the whistle and the match between {home_team.club_name} and {away_team.club_name} begins!"
    })
    
    # 2. Sort all goals and cards by minute
    all_events = []
    for g in goals:
        all_events.append((g.minute, "goal", g))
    for c in cards:
        all_events.append((c.minute, c.card_type, c))
        
    all_events.sort(key=lambda x: x[0])
    
    halftime_inserted = False
    for minute, etype, obj in all_events:
        # Half time insert
        if minute > 45 and not halftime_inserted:
            timeline.append({
                "minute": 45,
                "type": "half_time",
                "description": f"Half-Time: {home_team.club_name} {home_goals}–{away_goals} {away_team.club_name}."
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
            "description": f"Half-Time: {home_team.club_name} {home_goals}–{away_goals} {away_team.club_name}."
        })
        
    # 3. Full Time
    timeline.append({
        "minute": 90,
        "type": "full_time",
        "description": f"Full-Time: The referee blows the final whistle. Final score is {home_team.club_name} {home_goals}–{away_goals} {away_team.club_name}."
    })
    
    return timeline
