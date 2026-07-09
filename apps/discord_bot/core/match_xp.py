# apps/discord_bot/core/match_xp.py
"""Build per-card match XP payloads for process_match_result (US-23 AC-23e)."""
from __future__ import annotations

from typing import Any

from player_engine import match_xp_reward

from apps.discord_bot.core.card_payload import effective_card_age
from apps.discord_bot.core.debug_session_log import debug_log
from apps.discord_bot.core.match_runs import mark_match_xp_applied

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
            age=effective_card_age(card),
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


async def apply_match_xp_if_needed(
    db: Any,
    *,
    history_id: str,
    existing_row: dict | None,
    cards: list[dict],
    result_str: str,
    match_type: str,
    motm_name: str,
    key_events: list[dict],
    club_name: str,
    team_rating: float,
) -> None:
    """Apply process_match_result once per match_history row (crash-safe)."""
    if not cards:
        await mark_match_xp_applied(db, history_id)
        return
    if existing_row and existing_row.get("xp_applied_at"):
        return

    xp_payload = build_process_match_result_rpc(
        cards,
        result=result_str,
        match_type=match_type,
        motm_name=motm_name,
        key_events=key_events,
        club_name=club_name,
        team_rating=team_rating,
    )
    xp_payload["p_match_history_id"] = history_id
    # #region agent log
    debug_log(
        "A",
        "match_xp.py:apply_match_xp_if_needed",
        "pre process_match_result",
        {"history_id": str(history_id), "card_count": len(cards), "match_type": match_type},
    )
    # #endregion
    try:
        await db.rpc("process_match_result", xp_payload).execute()
        # #region agent log
        debug_log(
            "A",
            "match_xp.py:apply_match_xp_if_needed",
            "process_match_result ok",
            {"history_id": str(history_id)},
        )
        # #endregion
    except Exception as exc:
        # #region agent log
        debug_log(
            "A",
            "match_xp.py:apply_match_xp_if_needed",
            "process_match_result failed",
            {"history_id": str(history_id), "error": str(exc)[:300]},
        )
        # #endregion
        raise
    await mark_match_xp_applied(db, history_id)
