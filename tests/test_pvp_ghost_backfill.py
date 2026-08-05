# tests/test_pvp_ghost_backfill.py
"""Unit and pure logic tests for Instant PvP Backfill and Ghost Managers (Feature 054)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pvp.matchmaking import (
    ghost_candidate_score,
    is_backfill_eligible,
    is_ghost_snapshot_eligible,
)
from pvp.models import GhostSnapshot, QueueCandidate
from pvp.reward_policy import assert_lp_allowed, practice_lp_delta, pvp_lp_delta, reward_policy


def test_ghost_eligibility_and_scoring():
    now = datetime.now(timezone.utc)

    # Valid ghost snapshot
    snap = GhostSnapshot(
        owner_id=999111,
        club_name="Kathmandu Kings",
        global_lp=1400,
        global_division="Professional",
        division_rank=2,
        xi_rating=82.5,
        snapshot_json={"squad": [{"name": f"P{i}"} for i in range(11)]},
        captured_at=now - timedelta(hours=5),
        eligible=True,
    )

    assert is_ghost_snapshot_eligible(snap, seeker_id=888222, now=now) is True
    # Seeker self-snapshot excluded
    assert is_ghost_snapshot_eligible(snap, seeker_id=999111, now=now) is False

    # Stale snapshot (>7 days)
    stale_snap = snap.model_copy(update={"captured_at": now - timedelta(days=8)})
    assert is_ghost_snapshot_eligible(stale_snap, seeker_id=888222, now=now) is False

    # Ineligible flag
    disabled_snap = snap.model_copy(update={"eligible": False})
    assert is_ghost_snapshot_eligible(disabled_snap, seeker_id=888222, now=now) is False

    # Candidate scoring
    seeker = QueueCandidate(
        owner_id=888222,
        guild_id=1,
        global_division="Professional",
        division_rank=2,
        global_lp=1420,
        xi_rating=82.0,
        joined_at=now - timedelta(seconds=12),
    )

    score = ghost_candidate_score(seeker, snap)
    assert score[0] == 0  # Div rank delta
    assert abs(score[1] - 0.5) < 0.01  # OVR delta


def test_backfill_eligibility_threshold():
    now = datetime.now(timezone.utc)
    cand_recent = QueueCandidate(
        owner_id=111,
        guild_id=1,
        global_division="Professional",
        division_rank=2,
        global_lp=1400,
        xi_rating=80.0,
        joined_at=now - timedelta(seconds=4),
    )
    cand_eligible = QueueCandidate(
        owner_id=222,
        guild_id=1,
        global_division="Professional",
        division_rank=2,
        global_lp=1400,
        xi_rating=80.0,
        joined_at=now - timedelta(seconds=11),
    )

    assert is_backfill_eligible(cand_recent, now=now) is False
    assert is_backfill_eligible(cand_eligible, now=now) is True


def test_pvp_mode_reward_multipliers():
    # Live Human win
    res_live = reward_policy("pvp", "win", opponent_mode="live")
    assert res_live.coin_multiplier == 1.25
    assert res_live.xp_multiplier == 1.0
    assert res_live.rivalry_counted is True
    assert res_live.updates_pvp_record is True

    # Ghost win (0.85x coins, 0.90x XP)
    res_ghost = reward_policy("pvp", "win", opponent_mode="ghost", snapshot_age_seconds=3600)
    assert abs(res_ghost.coin_multiplier - 1.25 * 0.85) < 0.01
    assert res_ghost.xp_multiplier == 0.90
    assert res_ghost.rivalry_counted is False
    assert res_ghost.updates_pvp_record is False
    assert res_ghost.snapshot_age_seconds == 3600

    # AI Backfill win (0.70x coins, 0.75x XP)
    res_ai = reward_policy("pvp", "win", opponent_mode="ai_backfill")
    assert abs(res_ai.coin_multiplier - 1.25 * 0.70) < 0.01
    assert res_ai.xp_multiplier == 0.75
    assert res_ai.rivalry_counted is False

    # AI Practice (0 LP)
    res_practice = reward_policy("practice", "win")
    assert res_practice.rivalry_counted is False
    assert practice_lp_delta() == 0


def test_pvp_lp_delta_mode_scaling():
    # Live win base (+15 LP)
    new_lp, delta = pvp_lp_delta("win", current_lp=1000, opponent_mode="live", ranked_matches_completed=10)
    assert delta == 15

    # Ghost win (+15 * 0.75 = +11 LP)
    new_lp_ghost, delta_ghost = pvp_lp_delta("win", current_lp=1000, opponent_mode="ghost", ranked_matches_completed=10)
    assert delta_ghost == 11

    # AI Backfill win (+15 * 0.50 = +7 LP)
    new_lp_ai, delta_ai = pvp_lp_delta("win", current_lp=1000, opponent_mode="ai_backfill", ranked_matches_completed=10)
    assert delta_ai == 7

    # Ghost loss (-10 * 0.50 = -5 LP)
    _, delta_ghost_loss = pvp_lp_delta("loss", current_lp=1000, opponent_mode="ghost", ranked_matches_completed=10)
    assert delta_ghost_loss == -5

    # AI loss (-10 * 0.25 = -2 LP)
    _, delta_ai_loss = pvp_lp_delta("loss", current_lp=1000, opponent_mode="ai_backfill", ranked_matches_completed=10)
    assert delta_ai_loss == -2

    # Practice mode rejects non-zero LP
    with pytest.raises(ValueError):
        assert_lp_allowed("practice", 10)
