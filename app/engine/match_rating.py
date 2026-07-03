# app/engine/match_rating.py

import random
from app.engine.match_config import MatchEngineConfig
from app.engine.match_engine import (
    MatchTeamInput,
    MatchGoalEvent,
    MatchCardEvent,
    MatchSubstitutionEvent,
)

def calculate_player_ratings(
    rng: random.Random,
    home_team: MatchTeamInput,
    away_team: MatchTeamInput,
    home_goals: int,
    away_goals: int,
    goals: list[MatchGoalEvent],
    cards: list[MatchCardEvent],
    config: MatchEngineConfig,
    substitutions: list[MatchSubstitutionEvent] | None = None,
) -> dict[str, float]:
    """
    Computes player ratings based on match results, goals, assists, cards, and team clean sheets.
    """
    player_ratings = {}
    
    played_ids = set()
    played_ids.update(p.player_id for p in home_team.players)
    played_ids.update(p.player_id for p in away_team.players)
    if substitutions:
        played_ids.update(s.player_in_id for s in substitutions)

    def calculate_team_ratings(
        team: MatchTeamInput,
        goals_scored: int,
        goals_conceded: int,
        won: bool,
        drew: bool
    ):
        for p in team.players + team.bench:
            if p.player_id not in played_ids:
                continue

            # Base rating dynamically scaled by player consistency (Milestone F)
            consistency = getattr(p, "consistency", 70)
            if consistency is None:
                consistency = 70
            c_clamped = max(config.consistency_low_threshold, min(config.consistency_high_threshold, consistency))
            span = config.consistency_high_threshold - config.consistency_low_threshold
            frac = (c_clamped - config.consistency_low_threshold) / span if span > 0 else 1.0

            min_val = config.rating_base_min_low + frac * (config.rating_base_min_high - config.rating_base_min_low)
            max_val = config.rating_base_max_low + frac * (config.rating_base_max_high - config.rating_base_max_low)
            base = rng.uniform(min_val, max_val)
            
            # Scorer / Assist bonuses
            goals_count = sum(1 for g in goals if g.club_id == team.club_id and g.scorer_id == p.player_id)
            assists_count = sum(1 for g in goals if g.club_id == team.club_id and g.assist_id == p.player_id)
            
            base += goals_count * config.rating_scorer_bonus
            base += assists_count * config.rating_assist_bonus
            
            # GK and Defender clean sheet / concession adjustments
            slot = p.slot.upper()
            is_def_or_gk = (slot == "GK") or slot in ("LB", "CB1", "CB2", "CB3", "RB", "LWB", "RWB")
            if is_def_or_gk:
                if goals_conceded == 0:
                    base += config.rating_clean_sheet_bonus
                else:
                    base -= goals_conceded * config.rating_conceded_penalty
                    
            # Card penalties
            has_yellow = any(c.player_id == p.player_id and c.card_type == "yellow" for c in cards)
            has_red = any(c.player_id == p.player_id and c.card_type == "red" for c in cards)
            
            if has_yellow:
                base -= config.rating_yellow_card_penalty
            if has_red:
                base -= config.rating_red_card_penalty
                
            # Result modifiers
            if won:
                base += config.rating_win_bonus
            elif drew:
                base += config.rating_draw_bonus
            else:
                base -= config.rating_loss_penalty
                
            # Clamp player ratings strictly within configured bounds
            player_ratings[p.player_id] = round(max(config.rating_clamp_min, min(config.rating_clamp_max, base)), 1)
            
    home_won = home_goals > away_goals
    away_won = away_goals > home_goals
    drew = home_goals == away_goals
    
    calculate_team_ratings(home_team, home_goals, away_goals, home_won, drew)
    calculate_team_ratings(away_team, away_goals, home_goals, away_won, drew)
    
    return player_ratings

def select_motm(
    rng: random.Random,
    home_team: MatchTeamInput,
    away_team: MatchTeamInput,
    player_ratings: dict[str, float],
    home_won: bool,
    away_won: bool,
) -> str | None:
    """
    Selects the Man of the Match (MOTM) player ID based on ratings, resolving ties.
    """
    all_players = home_team.players + away_team.players
    if not all_players:
        return None
        
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
        # Prefer candidate from winning team
        winning_club_id = home_team.club_id if home_won else (away_team.club_id if away_won else None)
        if winning_club_id:
            winning_candidates = [c for c in candidates if c.player_id in [p.player_id for p in (home_team.players if winning_club_id == home_team.club_id else away_team.players)]]
            if winning_candidates:
                return rng.choice(winning_candidates).player_id
        return rng.choice(candidates).player_id
        
    return None
