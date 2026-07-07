# tests/test_league_standings.py
from __future__ import annotations

from leagues import compute_form, sort_standings, distribute_finish_prizes, familiarity_multiplier


def test_compute_form_last_five():
    fixtures = [
        {"is_played": True, "matchday": 1, "home_team_id": 1, "away_team_id": 2, "home_score": 2, "away_score": 0},
        {"is_played": True, "matchday": 2, "home_team_id": 3, "away_team_id": 1, "home_score": 1, "away_score": 1},
        {"is_played": True, "matchday": 3, "home_team_id": 1, "away_team_id": 4, "home_score": 0, "away_score": 1},
    ]
    assert compute_form(1, fixtures) == "WDL"


def test_sort_standings_h2h():
    rows = [
        {"discord_id": 1, "points": 6, "goal_difference": 2, "goals_for": 5},
        {"discord_id": 2, "points": 6, "goal_difference": 2, "goals_for": 5},
    ]
    fixtures = [
        {"is_played": True, "home_team_id": 1, "away_team_id": 2, "home_score": 2, "away_score": 0},
    ]
    ordered = sort_standings(rows, fixtures)
    assert ordered[0]["discord_id"] == 1


def test_distribute_finish_prizes():
    standings = [
        {"discord_id": 10, "is_ai": False},
        {"discord_id": 20, "is_ai": False},
        {"discord_id": 30, "is_ai": True},
    ]
    prizes = distribute_finish_prizes(standings, pool_base=1000, participation_coins=100)
    assert prizes[0].coins == 600
    assert prizes[1].coins == 250
    assert len(prizes) == 2


def test_familiarity_multiplier():
    assert familiarity_multiplier(0) == 1.0
    assert familiarity_multiplier(3) == 1.02
    assert familiarity_multiplier(3, heavy_rotation=True) == 1.01


def test_xi_streak_including_current():
    from leagues import xi_streak_including_current
    a, b = frozenset([1, 2]), frozenset([3, 4])
    assert xi_streak_including_current([a, a], a) == 3
    assert xi_streak_including_current([a, b], a) == 1
