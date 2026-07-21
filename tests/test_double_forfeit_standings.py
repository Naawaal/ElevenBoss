# tests/test_double_forfeit_standings.py
from __future__ import annotations

from leagues.forfeit_rules import double_forfeit, single_forfeit
from leagues.standings import apply_fixture_to_row, result_char
from leagues.seasonal_divisions import counts_for_promo_eligibility


def test_double_forfeit_deltas():
    out = double_forfeit()
    assert out.home_score == 0 and out.away_score == 0
    assert out.result_type == "double_forfeit"
    for side in (out.home, out.away):
        assert side.matches_played == 1
        assert side.lost == 1
        assert side.won == 0 and side.drawn == 0
        assert side.goals_for == 0 and side.goals_against == 0
        assert side.points == 0
        assert side.counts_as_draw is False
        assert side.counts_as_clean_sheet is False
        assert side.counts_as_unbeaten is False
        assert side.counts_as_appearance is False
        assert side.counts_for_promo_eligibility is False


def test_single_forfeit_3_0():
    out = single_forfeit(illegal_is_home=True)
    assert out.home_score == 0 and out.away_score == 3
    assert out.away.points == 3 and out.home.lost == 1


def test_standings_row_double_forfeit():
    row = {
        "matches_played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "goals_for": 5,
        "goals_against": 2,
        "goal_difference": 3,
        "points": 9,
    }
    apply_fixture_to_row(
        row,
        {
            "home_team_id": 1,
            "away_team_id": 2,
            "home_score": 0,
            "away_score": 0,
            "result_type": "double_forfeit",
            "is_played": True,
        },
        1,
    )
    assert row["matches_played"] == 1
    assert row["lost"] == 1
    assert row["points"] == 9
    assert row["goals_for"] == 5 and row["goals_against"] == 2
    assert row["goal_difference"] == 3


def test_form_char_double_forfeit_is_loss():
    assert result_char(1, 2, 1, 0, 0, result_type="double_forfeit") == "L"
    assert result_char(1, 2, 2, 0, 0, result_type="double_forfeit") == "L"


def test_promo_eligibility_excludes_double_forfeit():
    assert counts_for_promo_eligibility("double_forfeit") is False
    assert counts_for_promo_eligibility("void") is False
    assert counts_for_promo_eligibility("settled") is True
    assert counts_for_promo_eligibility(None) is True


def test_h2h_ignores_double_forfeit():
    from leagues.standings import head_to_head_points

    fixtures = [
        {
            "is_played": True,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_score": 0,
            "away_score": 0,
            "result_type": "double_forfeit",
        }
    ]
    assert head_to_head_points(1, 2, fixtures) == (0, 0)
