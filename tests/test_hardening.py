"""Hardening regression checks (no DB required)."""
from __future__ import annotations

from economy.engine import generate_agent_offer
from economy.config import GameConfig
from match_engine import get_slot_role


def test_get_slot_role_4231() -> None:
    assert get_slot_role("4-2-3-1", 1) == "GK"
    assert get_slot_role("4-2-3-1", 11) == "FWD"


def test_agent_offer_positive() -> None:
    cfg = GameConfig()
    offer = generate_agent_offer(80, "Rare", cfg)
    assert offer > 0


def test_agent_offer_matches_formula_monotonic() -> None:
    cfg = GameConfig()
    low = generate_agent_offer(60, "Common", cfg)
    high = generate_agent_offer(80, "Common", cfg)
    assert high > low
