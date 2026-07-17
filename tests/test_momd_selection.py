# tests/test_momd_selection.py
from __future__ import annotations

from leagues.momd import select_momd_winner


def test_picks_largest_manual_margin() -> None:
    fixtures = [
        {
            "id": "a",
            "is_played": True,
            "resolved_by": "manual",
            "home_team_id": 1,
            "away_team_id": 2,
            "home_score": 2,
            "away_score": 1,
            "home": {"is_ai": False},
            "away": {"is_ai": False},
        },
        {
            "id": "b",
            "is_played": True,
            "resolved_by": "manual",
            "home_team_id": 3,
            "away_team_id": 4,
            "home_score": 4,
            "away_score": 0,
            "home": {"is_ai": False},
            "away": {"is_ai": True},
        },
    ]
    w = select_momd_winner(fixtures)
    assert w is not None
    assert w.player_id == 3
    assert w.margin == 4
    assert w.fixture_id == "b"


def test_excludes_auto_sim() -> None:
    fixtures = [
        {
            "id": "a",
            "is_played": True,
            "resolved_by": "auto_sim",
            "home_team_id": 1,
            "away_team_id": 2,
            "home_score": 5,
            "away_score": 0,
            "home": {"is_ai": False},
            "away": {"is_ai": False},
        },
    ]
    assert select_momd_winner(fixtures) is None


def test_excludes_draw_and_ai_winner() -> None:
    fixtures = [
        {
            "id": "d",
            "is_played": True,
            "resolved_by": "manual",
            "home_team_id": 1,
            "away_team_id": 2,
            "home_score": 1,
            "away_score": 1,
            "home": {"is_ai": False},
            "away": {"is_ai": False},
        },
        {
            "id": "ai",
            "is_played": True,
            "resolved_by": "manual",
            "home_team_id": -1,
            "away_team_id": 5,
            "home_score": 3,
            "away_score": 0,
            "home": {"is_ai": True},
            "away": {"is_ai": False},
        },
    ]
    assert select_momd_winner(fixtures) is None


def test_tiebreak_gf_then_club_id() -> None:
    fixtures = [
        {
            "id": "x",
            "is_played": True,
            "resolved_by": "manual",
            "home_team_id": 20,
            "away_team_id": 21,
            "home_score": 3,
            "away_score": 1,
            "home": {"is_ai": False},
            "away": {"is_ai": False},
        },
        {
            "id": "y",
            "is_played": True,
            "resolved_by": "manual",
            "home_team_id": 10,
            "away_team_id": 11,
            "home_score": 2,
            "away_score": 0,
            "home": {"is_ai": False},
            "away": {"is_ai": False},
        },
    ]
    # Same margin 2; higher GF wins → club 20 (3 GF)
    w = select_momd_winner(fixtures)
    assert w is not None
    assert w.player_id == 20
