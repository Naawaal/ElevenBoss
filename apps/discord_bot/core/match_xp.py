# apps/discord_bot/core/match_xp.py
"""Build per-card match XP payloads for process_match_result (US-23 AC-23e)."""
from __future__ import annotations

from player_engine import match_xp_reward

MATCH_MINUTES = 90


def _goals_and_assists(
    player_name: str,
    club_name: str,
    key_events: list[dict],
) -> tuple[int, int]:
    goals = assists = 0
    for ev in key_events:
        if ev.get("type") != "GOAL":
            continue
        if ev.get("actor") == player_name and ev.get("team") == club_name:
            goals += 1
        if ev.get("assister") == player_name and ev.get("team") == club_name:
            assists += 1
    return goals, assists


def build_process_match_result_rpc(
    cards: list[dict],
    *,
    result: str,
    match_type: str,
    motm_name: str,
    key_events: list[dict],
    club_name: str,
    team_rating: float,
    minutes_played: int = MATCH_MINUTES,
) -> dict:
    """Return kwargs for Supabase RPC process_match_result with per-card XP."""
    card_ids: list = []
    xp_amounts: list[int] = []
    ratings: list[float] = []

    for card in cards:
        name = card["name"]
        goals, assists = _goals_and_assists(name, club_name, key_events)
        xp = match_xp_reward(
            minutes_played=minutes_played,
            match_rating=float(team_rating),
            match_type=match_type,
            goals=goals,
            assists=assists,
            motm=(name == motm_name),
            result=result,
        )
        card_ids.append(card["id"])
        xp_amounts.append(xp)
        ratings.append(float(team_rating))

    return {
        "p_result": result,
        "p_card_ids": card_ids,
        "p_xp_amount": xp_amounts[0] if xp_amounts else 0,
        "p_xp_amounts": xp_amounts,
        "p_card_ratings": ratings,
    }
