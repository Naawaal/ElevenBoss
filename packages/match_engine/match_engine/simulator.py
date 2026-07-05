# packages/match_engine/match_engine/simulator.py
from __future__ import annotations
import random
from .models import MatchInput, MatchResult

def simulate_match(match_input: MatchInput) -> MatchResult:
    """
    Simulates a match between the player's team and an AI opponent:
    - Team Rating = average overall rating of starting 11.
    - Applies a normal distribution modifier (±15%) to both ratings.
    - Higher modified rating wins; draw if difference is <= 3 points.
    - Calculates coins and points rewards.
    - Generates realistic goal scorelines matching the result.
    """
    my_players = match_input.my_players
    if not my_players:
        raise ValueError("Match requires at least one player card.")

    my_rating = sum(p.overall for p in my_players) / len(my_players)
    opp_rating = match_input.opponent_base_rating

    # Apply normal distribution modifier (±15% via std dev of 5% of rating)
    mod_my = my_rating * (1.0 + random.gauss(0.0, 0.05))
    mod_opp = opp_rating * (1.0 + random.gauss(0.0, 0.05))

    diff = mod_my - mod_opp

    if abs(diff) <= 3.0:
        result = "draw"
        goals = random.choice([0, 0, 1, 1, 2, 2, 3])
        goals_for = goals
        goals_against = goals
        coins_earned = 50
        points_earned = 1
    elif diff > 3.0:
        result = "win"
        # Determine winning margin based on diff
        margin = max(1, int(round(diff / 6.0)) + random.choice([0, 1]))
        goals_against = random.choice([0, 1, 2])
        goals_for = goals_against + margin
        coins_earned = 150
        points_earned = 3
    else:
        result = "loss"
        margin = max(1, int(round(abs(diff) / 6.0)) + random.choice([0, 1]))
        goals_for = random.choice([0, 1, 2])
        goals_against = goals_for + margin
        coins_earned = 0
        points_earned = 0

    # Generate possession based on the rating difference
    pos_base = 50 + int(diff * 1.5)
    pos_base = max(30, min(70, pos_base))
    possession_home = pos_base + random.randint(-5, 5)
    possession_home = max(20, min(80, possession_home))
    possession_away = 100 - possession_home

    # Generate shots correlated with possession and goals
    shots_home = max(goals_for + 1, int(possession_home * 0.25) + random.randint(-2, 4))
    shots_away = max(goals_against + 1, int(possession_away * 0.25) + random.randint(-2, 4))

    # Generate Man of the Match (MOTM)
    if result == "win" or (result == "draw" and random.random() > 0.5):
        motm = random.choice(my_players).name
    else:
        motm = "AI Opponent Star Player"

    return MatchResult(
        result=result,
        goals_for=goals_for,
        goals_against=goals_against,
        my_rating=round(my_rating, 2),
        opponent_rating=round(opp_rating, 2),
        coins_earned=coins_earned,
        points_earned=points_earned,
        possession_home=possession_home,
        possession_away=possession_away,
        shots_home=shots_home,
        shots_away=shots_away,
        motm=motm,
    )
