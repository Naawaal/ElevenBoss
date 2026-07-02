# app/engine/match_event_generator.py

import random
from app.engine.match_config import MatchEngineConfig
from app.engine.match_engine import (
    MatchTeamInput,
    MatchGoalEvent,
    MatchCardEvent,
    MatchPlayerInput,
)


def roll_cards_for_interval(
    rng: random.Random,
    team: MatchTeamInput,
    active_xi: list,
    interval_start: int,
    interval_end: int,
    config: MatchEngineConfig,
    foul_mult: float = 1.0,
) -> list[MatchCardEvent]:
    """
    Pure function: rolls for card events within a single match interval.

    Uses per-interval card rates from config (pre-scaled via
    ``1 - (1 - p_match)^(1/interval_count)`` to preserve expected full-match totals).
    Does NOT mutate any state — the caller is responsible for applying red card removals
    to the active XI.

    Args:
        rng: Local Random instance (deterministic).
        team: Original MatchTeamInput (used for club_id/club_name and player names).
        active_xi: Current active player list (may be shorter than 11 after prior red cards).
        interval_start: First minute of this interval (inclusive).
        interval_end: Last minute of this interval (inclusive).
        config: MatchEngineConfig with per-interval rate fields.
        foul_mult: Tactic foul probability multiplier (Milestone D). Scales the base
            per-interval yellow card rate. Defaults to 1.0 (neutral/BALANCED).

    Returns:
        List of MatchCardEvent instances generated in this interval.
    """
    cards: list[MatchCardEvent] = []
    yellow_counts: dict[str, int] = {}

    for p in active_xi:
        slot = p.slot.upper()

        # Select the per-interval rate based on position, then scale by tactic foul multiplier
        if slot == "GK":
            card_prob = config.gk_yellow_prob_interval
        elif slot in ("LB", "CB1", "CB2", "CB3", "RB", "LWB", "RWB", "LDM", "RDM", "CDM"):
            card_prob = config.def_dm_yellow_prob_interval
        else:
            card_prob = config.other_yellow_prob_interval
        card_prob = card_prob * foul_mult  # tactic foul multiplier (BALANCED=1.0, HIGH_PRESS=1.30, …)

        # Roll for yellow card
        if rng.random() < card_prob:
            minute = rng.randint(interval_start, interval_end)
            desc = f"Yellow card shown to {p.name} ({team.club_name}) for a tactical foul."
            cards.append(MatchCardEvent(
                minute=minute,
                club_id=team.club_id,
                player_id=p.player_id,
                card_type="yellow",
                description=desc,
            ))
            yellow_counts[p.player_id] = yellow_counts.get(p.player_id, 0) + 1

            # Double yellow -> red (second yellow within this same interval)
            if yellow_counts[p.player_id] == 2:
                red_min = min(interval_end, minute + rng.randint(config.double_yellow_min_gap, config.double_yellow_max_gap))
                desc_red = f"Red card! {p.name} ({team.club_name}) is sent off after a second yellow card."
                cards.append(MatchCardEvent(
                    minute=red_min,
                    club_id=team.club_id,
                    player_id=p.player_id,
                    card_type="red",
                    description=desc_red,
                ))

        # Direct red card roll (per-interval rate)
        elif rng.random() < config.direct_red_prob_interval:
            minute = rng.randint(interval_start, interval_end)
            desc = f"Red card! {p.name} ({team.club_name}) is sent off for a dangerous tackle."
            cards.append(MatchCardEvent(
                minute=minute,
                club_id=team.club_id,
                player_id=p.player_id,
                card_type="red",
                description=desc,
            ))

    return cards


def _get_scorer_weight(slot: str, weights_dict: dict[str, float]) -> float:
    """Helper to resolve a player's scorer weight from a weights dictionary."""
    slot = slot.upper()
    if slot.startswith("ST") or slot.startswith("CF"):
        return weights_dict.get("ST", 100.0)
    elif slot in ("LW", "RW"):
        return weights_dict.get("LW", 80.0)
    elif slot in ("CAM",):
        return weights_dict.get("CAM", 60.0)
    elif slot in ("LM", "RM") or slot.startswith("CM"):
        return weights_dict.get("LM", 30.0)
    elif slot in ("LDM", "RDM", "CDM"):
        return weights_dict.get("LDM", 15.0)
    elif slot == "GK":
        return weights_dict.get("GK", 0.01)
    else:
        # Check specific CB, LB, RB, etc. keys first for tables like own_goal_scorer_weights
        for key in ("CB", "LB", "RB", "LWB", "RWB"):
            if slot.startswith(key) and key in weights_dict:
                return weights_dict[key]
        return weights_dict.get("DEFENDER", 5.0)


def _attribute_assist(
    rng: random.Random,
    team: MatchTeamInput,
    scorer: MatchPlayerInput,
    config: MatchEngineConfig,
) -> MatchPlayerInput | None:
    """Helper to attribute an assist provider for a goal from the rest of the team."""
    if rng.random() >= config.assist_probability or len(team.players) <= 1:
        return None
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
        return rng.choices(assist_candidates, weights=assist_weights, k=1)[0]
    return None


def attribute_goal(
    rng: random.Random,
    team: MatchTeamInput,
    opponent: MatchTeamInput,
    minute: int,
    config: MatchEngineConfig,
) -> MatchGoalEvent:
    """
    Selects a scorer, assist provider, and goal source for a team's goal using config weights,
    supporting Milestone F goal sources (open_play, set_piece, penalty, own_goal).
    """
    from app.engine.team_strength import calculate_team_strength
    from app.engine.match_engine import MatchPlayerInput

    # Recompute strengths to evaluate defensive pressure deficit
    team_str = calculate_team_strength(team.formation, team.players, is_home=team.is_home, config=config)
    opp_str = calculate_team_strength(opponent.formation, opponent.players, is_home=opponent.is_home, config=config)

    deficit = max(0.0, team_str.attack - opp_str.defense)
    own_goal_prob = config.own_goal_base_probability * (1.0 + deficit * config.own_goal_deficit_multiplier)

    # 1. Roll for own goal
    if rng.random() < own_goal_prob:
        scorer_candidates = []
        scorer_weights = []
        for p in opponent.players:
            w = _get_scorer_weight(p.slot, config.own_goal_scorer_weights)
            scorer_candidates.append(p)
            scorer_weights.append(w)
        scorer = rng.choices(scorer_candidates, weights=scorer_weights, k=1)[0]
        assist = None
        goal_source = "own_goal"
        desc = f"Own Goal! {scorer.name} ({opponent.club_name}) accidentally puts it into their own net."

    # 2. Roll for penalty
    elif rng.random() < config.penalty_probability_per_match:
        scorer_candidates = []
        scorer_weights = []
        for p in team.players:
            w = _get_scorer_weight(p.slot, config.penalty_scorer_weights)
            scorer_candidates.append(p)
            scorer_weights.append(w)
        scorer = rng.choices(scorer_candidates, weights=scorer_weights, k=1)[0]
        assist = None
        goal_source = "penalty"
        desc = f"Goal! {scorer.name} converts the penalty for {team.club_name}."

    # 3. Roll for set piece
    elif rng.random() < config.set_piece_goal_probability:
        scorer_candidates = []
        scorer_weights = []
        for p in team.players:
            w = _get_scorer_weight(p.slot, config.set_piece_scorer_weights)
            scorer_candidates.append(p)
            scorer_weights.append(w)
        scorer = rng.choices(scorer_candidates, weights=scorer_weights, k=1)[0]
        assist = _attribute_assist(rng, team, scorer, config)
        goal_source = "set_piece"
        desc = f"Goal! {scorer.name} scores from a set piece for {team.club_name}."
        if assist:
            desc += f" Assisted by {assist.name}."

    # 4. Fallback to open play
    else:
        scorer_candidates = []
        scorer_weights = []
        for p in team.players:
            w = _get_scorer_weight(p.slot, config.scorer_weights)
            scorer_candidates.append(p)
            scorer_weights.append(w)
        scorer = rng.choices(scorer_candidates, weights=scorer_weights, k=1)[0]
        assist = _attribute_assist(rng, team, scorer, config)
        goal_source = "open_play"
        desc = f"Goal! {scorer.name} scores for {team.club_name}."
        if assist:
            desc += f" Assisted by {assist.name}."

    return MatchGoalEvent(
        minute=minute,
        club_id=team.club_id,
        scorer_id=scorer.player_id,
        assist_id=assist.player_id if assist else None,
        description=desc,
        goal_source=goal_source
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
    substitutions: list | None = None,
    injuries: list | None = None,
) -> list[dict]:
    """
    Builds the chronological timeline event list for display.

    Args:
        substitutions: Optional list of MatchSubstitutionEvent instances (Milestone B+).
        injuries:      Optional list of MatchInjuryEvent instances (Milestone B+).
    Both default to empty so callers from earlier milestones are unchanged.
    """
    timeline = []
    
    # 1. Match Start
    timeline.append({
        "minute": 0,
        "type": "match_start",
        "description": f"The referee blows the whistle and the match between {home_team.club_name} and {away_team.club_name} begins!"
    })
    
    # 2. Merge all timed events (goals, cards, subs, injuries) and sort chronologically
    all_events = []
    for g in goals:
        all_events.append((g.minute, "goal", g))
    for c in cards:
        all_events.append((c.minute, c.card_type, c))
    for s in (substitutions or []):
        all_events.append((s.minute, "substitution", s))
    for inj in (injuries or []):
        all_events.append((inj.minute, "injury", inj))

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
            
        if etype == "goal":
            entry = {
                "minute": minute,
                "type": etype,
                "description": obj.description,
                "club_id": obj.club_id,
                "player_id": getattr(obj, "scorer_id", None),
                "secondary_player_id": getattr(obj, "assist_id", None),
            }
        elif etype in ("yellow", "red"):
            entry = {
                "minute": minute,
                "type": etype,
                "description": obj.description,
                "club_id": obj.club_id,
                "player_id": obj.player_id,
                "secondary_player_id": None,
            }
        elif etype == "substitution":
            entry = {
                "minute": minute,
                "type": etype,
                "description": obj.description,
                "club_id": obj.club_id,
                "player_id": obj.player_out_id,
                "secondary_player_id": obj.player_in_id,
                "reason": obj.reason,
            }
        else:  # injury
            entry = {
                "minute": minute,
                "type": etype,
                "description": obj.description,
                "club_id": obj.club_id,
                "player_id": obj.player_id,
                "secondary_player_id": None,
            }
        timeline.append(entry)
        
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
