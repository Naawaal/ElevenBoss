# tests/test_progression.py
from __future__ import annotations

from player_engine import (
    L_MAX,
    POINTS_PER_LEVEL,
    calculate_level,
    can_allocate_skill_point,
    cumulative_xp_for_level,
    drill_unlocked,
    drill_xp_reward,
    evolution_unlocked,
    fusion_xp_reward,
    level_from_xp,
    match_xp_reward,
    simulate_apply_card_xp,
    skill_points_earned_for_level,
    track_min_player_level,
    xp_needed_for_level,
    xp_progress,
)


def test_xp_curve_matches_calculate_level() -> None:
    for xp in (0, 99, 100, 211, 212, 337, 1475):
        assert level_from_xp(xp) == calculate_level(xp)


def test_level_cap_at_l_max() -> None:
    max_xp = cumulative_xp_for_level(L_MAX)
    assert level_from_xp(max_xp) == L_MAX
    assert level_from_xp(max_xp + 999_999) == L_MAX


def test_xp_needed_milestones() -> None:
    assert xp_needed_for_level(1) == 100
    assert xp_needed_for_level(2) == 112
    assert cumulative_xp_for_level(5) == 477
    assert cumulative_xp_for_level(10) == 1475


def test_xp_progress() -> None:
    level, curr, needed = xp_progress(150)
    assert level == 2
    assert curr == 50
    assert needed == 112


def test_skill_points_earned() -> None:
    assert skill_points_earned_for_level(1) == 0
    assert skill_points_earned_for_level(10) == 27
    assert skill_points_earned_for_level(10) == (10 - 1) * POINTS_PER_LEVEL


def test_simulate_apply_card_xp_level_up() -> None:
    result = simulate_apply_card_xp(99, 5)
    assert result.old_level == 1
    assert result.new_level == 2
    assert result.levels_gained == 1
    assert result.skill_points_granted == POINTS_PER_LEVEL
    assert result.new_xp == 104


def test_simulate_apply_card_xp_wasted_at_max() -> None:
    max_xp = cumulative_xp_for_level(L_MAX)
    result = simulate_apply_card_xp(max_xp, 500)
    assert result.new_level == L_MAX
    assert result.levels_gained == 0
    assert result.skill_points_granted == 0
    assert result.xp_wasted == 500


def test_fusion_xp_monotonic() -> None:
    low = fusion_xp_reward(1, 50)
    high = fusion_xp_reward(10, 80)
    assert high > low


def test_drill_diminishing_returns() -> None:
    assert drill_xp_reward(25, 1) == 25
    assert drill_xp_reward(25, 10) < drill_xp_reward(25, 1)


def test_match_xp_clamped() -> None:
    xp = match_xp_reward(
        minutes_played=90,
        match_rating=9.5,
        match_type="league",
        goals=3,
        assists=2,
        motm=True,
        result="win",
    )
    assert 1 <= xp <= 35


def test_drill_and_evolution_gates() -> None:
    assert drill_unlocked("pac_sprint", 1)
    assert not drill_unlocked("pac_sprint", 0)
    assert evolution_unlocked("pace_boost", 5)
    assert not evolution_unlocked("shooting_star", 9)
    assert track_min_player_level("def_wall") == 8


def test_can_allocate_skill_point_at_pot() -> None:
    stats = {"pac": 60, "sho": 60, "pas": 60, "dri": 60, "def": 60, "phy": 60}
    ok, reason = can_allocate_skill_point(
        position="FWD",
        stats=stats,
        playstyles=[],
        potential=60,
        stat_key="sho",
        overall=60,
    )
    assert not ok
    assert "potential" in reason.lower()
