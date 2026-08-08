# tests/test_player_suspensions.py
"""Feature 057 US4 — dismissal payload mapping (RPC integration is migration-level)."""
from __future__ import annotations

from types import SimpleNamespace

from apps.discord_bot.core.competitive_match import dismissals_for_rpc
from match_engine.models import MatchPlayerCard


def test_dismissals_for_rpc_maps_home_card_ids():
    squad = [
        MatchPlayerCard(name="Alex Goal", position="ST", overall=70, card_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        MatchPlayerCard(name="Ben Mid", position="CM", overall=68, card_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    ]
    state = SimpleNamespace(
        dismissals=[
            {"reason": "second_yellow", "player_name": "Alex Goal", "team": "Home FC"},
            {"reason": "straight_red", "player_name": "Bot Striker", "team": "AI Club"},
        ]
    )
    payload = dismissals_for_rpc(state, squad)
    assert len(payload) == 1
    assert payload[0]["player_card_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert payload[0]["reason"] == "second_yellow"
