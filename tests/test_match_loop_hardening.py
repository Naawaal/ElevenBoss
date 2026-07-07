# tests/test_match_loop_hardening.py
"""US-29 — bot/friendly match XP and economy helpers."""
from __future__ import annotations

from apps.discord_bot.core.economy_rpc import (
    compute_bot_match_coins,
    compute_friendly_match_coins,
    match_energy_cost,
)
from apps.discord_bot.core.match_xp import build_process_match_result_rpc


def test_bot_match_energy_cost_v2() -> None:
    assert match_energy_cost("bot", v2=True) == 20
    assert match_energy_cost("friendly", v2=True) == 15


def test_friendly_match_coins_winner_only() -> None:
    assert compute_friendly_match_coins("win", v2=True) > 0
    assert compute_friendly_match_coins("loss", v2=True) == 0
    assert compute_friendly_match_coins("draw", v2=True) == 0


def test_bot_match_coins_use_config_not_inline_loss() -> None:
    win = compute_bot_match_coins("win", division_win_coins=100, v2=True)
    draw = compute_bot_match_coins("draw", division_win_coins=100, v2=True)
    loss = compute_bot_match_coins("loss", division_win_coins=100, v2=True)
    assert win > draw >= loss
    assert loss != 15  # old hardcoded consolation


def test_build_process_match_result_rpc_friendly_type() -> None:
    cards = [{"id": "aaa", "name": "Striker"}]
    payload = build_process_match_result_rpc(
        cards,
        result="win",
        match_type="friendly",
        motm_name="Striker",
        key_events=[],
        club_name="FC Test",
        team_rating=7.0,
    )
    assert payload["p_xp_amounts"]
    assert payload["p_card_ratings"] == [7.0]
