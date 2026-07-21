# tests/test_league_time_defaults_freeze.py
from __future__ import annotations

from leagues.league_time import (
    DEFAULT_RESOLUTION_HOUR,
    DEFAULT_TIMEZONE,
    coalesce_league_time,
    guild_setting_must_not_rewrite_season_snapshot,
)


def test_coalesce_null_to_utc_midnight() -> None:
    eff = coalesce_league_time(None, None)
    assert eff.timezone == DEFAULT_TIMEZONE == "UTC"
    assert eff.resolution_hour_local == DEFAULT_RESOLUTION_HOUR == 0
    assert eff.used_defaults is True


def test_coalesce_partial_timezone_only() -> None:
    eff = coalesce_league_time("Europe/London", None)
    assert eff.timezone == "Europe/London"
    assert eff.resolution_hour_local == 0
    assert eff.used_defaults is True


def test_coalesce_explicit_keeps_values() -> None:
    eff = coalesce_league_time("Asia/Kathmandu", 20)
    assert eff.timezone == "Asia/Kathmandu"
    assert eff.resolution_hour_local == 20
    assert eff.used_defaults is False


def test_freeze_policy_predicate() -> None:
    # Guild League Time upserts must never rewrite frozen season/matchday windows.
    assert guild_setting_must_not_rewrite_season_snapshot() is True


def test_freeze_field_mapping_shape() -> None:
    """Prepare freezes effective values onto season columns (contract shape)."""
    eff = coalesce_league_time(None, None)
    snapshot = {
        "timezone": eff.timezone,
        "resolution_hour_local": eff.resolution_hour_local,
    }
    assert snapshot == {"timezone": "UTC", "resolution_hour_local": 0}
