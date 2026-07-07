# tests/test_match_points.py
from leagues import (
    clamp_global_lp,
    division_rank_points,
    global_lp_delta,
    season_fixture_points,
)


def test_division_rank_points() -> None:
    assert division_rank_points("win") == 3
    assert division_rank_points("draw") == 1
    assert division_rank_points("loss") == 0


def test_season_fixture_points_matches_football() -> None:
    assert season_fixture_points("win") == division_rank_points("win")


def test_global_lp_delta() -> None:
    assert global_lp_delta("win") == 15
    assert global_lp_delta("draw") == 5
    assert global_lp_delta("loss") == -10


def test_clamp_global_lp_floor() -> None:
    new_lp, actual = clamp_global_lp(5, -10)
    assert new_lp == 0
    assert actual == -5


def test_clamp_global_lp_normal() -> None:
    new_lp, actual = clamp_global_lp(100, 15)
    assert new_lp == 115
    assert actual == 15
