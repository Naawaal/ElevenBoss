# tests/test_match_xp.py
from apps.discord_bot.core.match_xp import build_process_match_result_rpc


def test_build_process_match_result_rpc_per_card() -> None:
    cards = [
        {"id": "aaa", "name": "Striker"},
        {"id": "bbb", "name": "Midfielder"},
    ]
    events = [
        {"type": "GOAL", "actor": "Striker", "team": "FC Test", "assister": "Midfielder"},
    ]
    payload = build_process_match_result_rpc(
        cards,
        result="win",
        match_type="bot",
        motm_name="Striker",
        key_events=events,
        club_name="FC Test",
        team_rating=7.5,
    )
    assert payload["p_card_ids"] == ["aaa", "bbb"]
    assert len(payload["p_xp_amounts"]) == 2
    assert payload["p_xp_amounts"][0] > payload["p_xp_amounts"][1]
