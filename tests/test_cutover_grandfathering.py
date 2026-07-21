# tests/test_cutover_grandfathering.py
from __future__ import annotations

from leagues.cutover import (
    can_start_v1_season,
    has_blocking_non_v1_open_season,
    lifecycle_v1_effective,
)


def test_effective_flag_truth_table():
    assert lifecycle_v1_effective(global_flag=False, guild_flag=None) is False
    assert lifecycle_v1_effective(global_flag=False, guild_flag=True) is False
    assert lifecycle_v1_effective(global_flag=True, guild_flag=None) is True
    assert lifecycle_v1_effective(global_flag=True, guild_flag=True) is True
    assert lifecycle_v1_effective(global_flag=True, guild_flag=False) is False


def test_blocks_when_dynamics_season_open():
    seasons = [
        {"status": "active", "pacing_mode": "dynamics", "ruleset_version": None},
    ]
    assert has_blocking_non_v1_open_season(seasons) is True
    assert can_start_v1_season(effective_cutover=True, open_seasons=seasons) is False


def test_allows_when_only_completed_legacy():
    seasons = [
        {"status": "completed", "pacing_mode": "dynamics", "ruleset_version": None},
    ]
    assert has_blocking_non_v1_open_season(seasons) is False
    assert can_start_v1_season(effective_cutover=True, open_seasons=seasons) is True


def test_blocks_second_open_v1():
    seasons = [
        {"status": "registration_open", "pacing_mode": "lifecycle_v1", "ruleset_version": "lifecycle-v1"},
    ]
    assert can_start_v1_season(effective_cutover=True, open_seasons=seasons) is False


def test_cutover_off_cannot_start():
    assert can_start_v1_season(effective_cutover=False, open_seasons=[]) is False
