# tests/test_weekly_tiers.py
from datetime import datetime, timezone

from leagues import highest_unclaimed_tier, iso_week_utc, tier_progress_label, tiers_reached, weekly_tier_coin_reward


def test_tiers_reached() -> None:
    assert tiers_reached(18) == ["bronze", "silver", "gold"]
    assert tiers_reached(5) == []


def test_highest_unclaimed() -> None:
    assert highest_unclaimed_tier(12, set()) == "silver"
    assert highest_unclaimed_tier(12, {"bronze", "silver"}) is None


def test_weekly_tier_coins_scale() -> None:
    assert weekly_tier_coin_reward("bronze", "Legendary") > weekly_tier_coin_reward("bronze", "Grassroots")


def test_tier_progress_label_all_complete() -> None:
    assert tier_progress_label(18) == "Bronze ✓ · Silver ✓ · Gold ✓"
    assert tier_progress_label(5) == "5/6 Bronze"
    assert tier_progress_label(12) == "Bronze ✓ · Silver ✓ · 12/18 Gold"


def test_iso_week_zero_padded_matches_postgres() -> None:
    # Postgres claim_weekly_rank_tier uses to_char(..., 'IYYY-"W"IW')
    dt = datetime(2026, 2, 16, tzinfo=timezone.utc)
    assert iso_week_utc(dt) == "2026-W08"
    dt2 = datetime(2026, 1, 5, tzinfo=timezone.utc)
    assert iso_week_utc(dt2) == "2026-W02"
