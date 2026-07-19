# tests/test_match_xp.py
from apps.discord_bot.core.match_xp import (
    MatchXpApplyResult,
    build_process_match_result_rpc,
    format_match_xp_line,
)


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


def test_format_match_xp_line_granted() -> None:
    line = format_match_xp_line(
        MatchXpApplyResult(total_granted=330, cards_granted=11, attempted=True)
    )
    assert line is not None
    assert "+330" in line
    assert "11 players" in line


def test_format_match_xp_line_daily_cap() -> None:
    line = format_match_xp_line(MatchXpApplyResult(total_granted=0, attempted=True))
    assert line is not None
    assert "daily cap" in line.lower()
    assert "0" in line


def test_format_match_xp_line_skipped() -> None:
    assert format_match_xp_line(MatchXpApplyResult(skipped=True)) is None
    assert format_match_xp_line(None) is None
