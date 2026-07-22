"""US-42.6 marketplace integrity source guards."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG_062 = ROOT / "supabase" / "migrations" / "062_p2p_transfer_market.sql"
MIG_075 = ROOT / "supabase" / "migrations" / "075_player_card_state_guards.sql"
SMOKE = ROOT / "scratch" / "smoke_transfer_market.py"
RACE_TEST = ROOT / "tests" / "test_transfer_market_race.py"


def test_purchase_rpc_lock_own_buy_and_keys():
    text = MIG_062.read_text(encoding="utf-8")
    assert "purchase_transfer_listing" in text
    assert "FOR UPDATE" in text
    assert "Cannot buy your own listing" in text
    assert "transfer_buy:" in text
    assert "transfer_sale:" in text


def test_listing_statuses_and_expire_fn():
    text = MIG_062.read_text(encoding="utf-8")
    for s in ("active", "sold", "cancelled", "expired"):
        assert s in text
    assert "expire_stale_transfer_listings" in text


def test_create_listing_uses_card_state_assert():
    text = MIG_075.read_text(encoding="utf-8")
    assert "list_transfer" in text
    assert "assert_card_action_allowed" in text
    assert "create_transfer_listing" in text


def test_race_coverage_documented():
    assert RACE_TEST.is_file()
    race = RACE_TEST.read_text(encoding="utf-8")
    assert "purchase_transfer_listing" in race or "tax" in race
    assert SMOKE.is_file() or "smoke_transfer_market" in race
