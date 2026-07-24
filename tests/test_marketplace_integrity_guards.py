"""US-42.6 marketplace integrity source guards."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG_062 = ROOT / "supabase" / "migrations" / "062_p2p_transfer_market.sql"
MIG_075 = ROOT / "supabase" / "migrations" / "075_player_card_state_guards.sql"
MIG_086 = ROOT / "supabase" / "migrations" / "086_marketplace_intelligence.sql"
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


def test_086_purchase_writes_sale_snapshots_and_ownership():
    text = MIG_086.read_text(encoding="utf-8")
    assert "fair_value_coins" in text
    assert "age_at_sale" in text
    assert "compute_agent_offer" in text
    assert "INSERT INTO public.transfer_sales_log" in text
    assert "card_ownership_history" in text
    assert "ended_via = 'p2p_transfer'" in text
    assert "Cannot buy your own listing" in text
    assert "FOR UPDATE" in text
    assert "transfer_buy:" in text
    assert "transfer_sale:" in text


def test_086_agent_sale_closes_ownership_before_delete():
    text = MIG_086.read_text(encoding="utf-8")
    agent_idx = text.index("CREATE OR REPLACE FUNCTION public.process_agent_sale")
    delete_idx = text.index("DELETE FROM public.player_cards WHERE id = p_card_id;", agent_idx)
    close_idx = text.index("ended_via = 'agent_sale'", agent_idx)
    assert close_idx < delete_idx


def test_086_discovery_and_analytics_rpcs():
    text = MIG_086.read_text(encoding="utf-8")
    assert "get_price_discovery" in text
    assert "insufficient_data" in text
    assert "get_market_analytics" in text
    assert "daily_volume" in text
    assert "tax_removed" in text
