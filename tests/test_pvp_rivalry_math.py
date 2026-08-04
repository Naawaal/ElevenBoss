# tests/test_pvp_rivalry_math.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pvp.rivalry_math import (
    apply_ranked_meeting,
    badge_keys_earned,
    canonical_pair,
    refresh_dormancy,
)
from pvp.models import RivalryState


def test_canonical_pair() -> None:
    assert canonical_pair(5, 2) == (2, 5)


def test_activate_on_third_meeting_within_30d() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = RivalryState(manager_a_id=1, manager_b_id=2)
    state, _ = apply_ranked_meeting(
        state, winner_id=1, home_id=1, away_id=2, home_goals=2, away_goals=1, matched_at=t0
    )
    assert state.status == "tracking"
    state, _ = apply_ranked_meeting(
        state,
        winner_id=2,
        home_id=1,
        away_id=2,
        home_goals=0,
        away_goals=1,
        matched_at=t0 + timedelta(days=2),
    )
    state, events = apply_ranked_meeting(
        state,
        winner_id=1,
        home_id=1,
        away_id=2,
        home_goals=3,
        away_goals=1,
        matched_at=t0 + timedelta(days=5),
    )
    assert state.status == "active"
    assert state.meetings == 3
    assert any(e.code == "rivalry_activated" for e in events)
    assert "first_rival" in badge_keys_earned(state, events)


def test_dormant_after_60_days() -> None:
    last = datetime.now(timezone.utc) - timedelta(days=61)
    state = RivalryState(
        manager_a_id=1,
        manager_b_id=2,
        meetings=5,
        status="active",
        last_match_at=last,
    )
    assert refresh_dormancy(state).status == "dormant"


def test_streak_break_revenge() -> None:
    t0 = datetime(2026, 2, 1, tzinfo=timezone.utc)
    state = RivalryState(
        manager_a_id=1,
        manager_b_id=2,
        meetings=3,
        a_wins=3,
        status="active",
        current_streak_owner=1,
        current_streak_count=3,
        activated_at=t0,
        last_match_at=t0,
        first_meeting_in_window_at=t0,
    )
    state, events = apply_ranked_meeting(
        state,
        winner_id=2,
        home_id=1,
        away_id=2,
        home_goals=0,
        away_goals=1,
        matched_at=t0 + timedelta(days=1),
    )
    codes = {e.code for e in events}
    assert "streak_broken" in codes
    assert "revenge_served" in codes
    assert "streak_breaker" in badge_keys_earned(state, events)
    assert "revenge_served" in badge_keys_earned(state, events)


def test_lead_change_and_series_tied() -> None:
    t0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    # First decisive meeting from 0–0 → lead_changed
    state = RivalryState(
        manager_a_id=1,
        manager_b_id=2,
        meetings=2,
        a_wins=0,
        b_wins=0,
        draws=2,
        status="active",
        activated_at=t0,
        last_match_at=t0,
        first_meeting_in_window_at=t0,
    )
    state, events = apply_ranked_meeting(
        state,
        winner_id=1,
        home_id=1,
        away_id=2,
        home_goals=2,
        away_goals=0,
        matched_at=t0 + timedelta(days=1),
    )
    assert any(e.code == "lead_changed" for e in events)
    # B equalizes → series_tied
    state, events = apply_ranked_meeting(
        state,
        winner_id=2,
        home_id=1,
        away_id=2,
        home_goals=0,
        away_goals=1,
        matched_at=t0 + timedelta(days=2),
    )
    assert state.a_wins == state.b_wins == 1
    assert any(e.code == "series_tied" for e in events)


def test_milestones_and_old_enemies_badge() -> None:
    t0 = datetime(2026, 4, 1, tzinfo=timezone.utc)
    state = RivalryState(
        manager_a_id=1,
        manager_b_id=2,
        meetings=9,
        a_wins=5,
        b_wins=4,
        status="active",
        activated_at=t0,
        last_match_at=t0,
        first_meeting_in_window_at=t0,
    )
    state, events = apply_ranked_meeting(
        state,
        winner_id=1,
        home_id=1,
        away_id=2,
        home_goals=1,
        away_goals=0,
        matched_at=t0 + timedelta(days=1),
    )
    assert state.meetings == 10
    assert any(e.code == "tenth_meeting" for e in events)
    badges = badge_keys_earned(state, events)
    assert "old_enemies" in badges
    assert "rivalry_leader" in badges


def test_three_win_streak_event() -> None:
    t0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
    state = RivalryState(
        manager_a_id=1,
        manager_b_id=2,
        meetings=5,
        a_wins=2,
        status="active",
        current_streak_owner=1,
        current_streak_count=2,
        activated_at=t0,
        last_match_at=t0,
        first_meeting_in_window_at=t0,
    )
    state, events = apply_ranked_meeting(
        state,
        winner_id=1,
        home_id=1,
        away_id=2,
        home_goals=2,
        away_goals=0,
        matched_at=t0 + timedelta(days=1),
    )
    assert state.current_streak_count == 3
    assert any(e.code == "three_win_streak" for e in events)
