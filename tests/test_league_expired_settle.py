# tests/test_league_expired_settle.py
"""048 expired fixture settle decision + Fixtures labels."""
from __future__ import annotations

from leagues import (
    ExpiredSettleMode,
    decide_expired_settle,
    double_forfeit,
    played_fixture_status_label,
    single_forfeit,
)


def test_decide_both_ok_sim():
    assert decide_expired_settle(home_ok=True, away_ok=True) == ExpiredSettleMode.SIM


def test_decide_home_illegal_forfeit_home():
    assert (
        decide_expired_settle(home_ok=False, away_ok=True)
        == ExpiredSettleMode.FORFEIT_HOME
    )


def test_decide_away_illegal_forfeit_away():
    assert (
        decide_expired_settle(home_ok=True, away_ok=False)
        == ExpiredSettleMode.FORFEIT_AWAY
    )


def test_decide_both_illegal_double():
    assert (
        decide_expired_settle(home_ok=False, away_ok=False)
        == ExpiredSettleMode.DOUBLE_FORFEIT
    )


def test_forfeit_scorelines_match_026():
    # Callers treat AI as always-ok; humans use human_club_xi_ok.
    home_illegal = single_forfeit(illegal_is_home=True)
    assert (home_illegal.home_score, home_illegal.away_score) == (0, 3)
    assert home_illegal.result_type == "forfeit"

    away_illegal = single_forfeit(illegal_is_home=False)
    assert (away_illegal.home_score, away_illegal.away_score) == (3, 0)

    both = double_forfeit()
    assert (both.home_score, both.away_score) == (0, 0)
    assert both.result_type == "double_forfeit"


def test_played_fixture_status_labels():
    # Fixtures hub: **H - A** ({label}) — see league_cog show_fixtures
    assert played_fixture_status_label("forfeit") == "Forfeit"
    assert played_fixture_status_label("double_forfeit") == "Double Forfeit"
    assert played_fixture_status_label("settled") == "Full Time"
    assert played_fixture_status_label(None) == "Full Time"
