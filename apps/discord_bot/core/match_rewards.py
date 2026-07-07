# apps/discord_bot/core/match_rewards.py
"""Bot and friendly match rewards — economy v2, XP, ladder stats (US-29)."""
from __future__ import annotations

from typing import Any

from apps.discord_bot.core.economy_rpc import (
    apply_match_economy,
    compute_bot_match_coins,
    compute_friendly_match_coins,
    economy_v2_enabled,
    match_energy_cost,
    sync_action_energy,
)
from apps.discord_bot.core.match_xp import apply_match_xp_if_needed


async def apply_bot_match_rewards(
    db: Any,
    *,
    player_id: int,
    player_row: dict,
    result_str: str,
    cards: list[dict],
    club_name: str,
    team_rating: float,
    opponent_rating: float,
    goals_for: int,
    goals_against: int,
    points_earned: int,
    lp_change: int,
    division_win_coins: int,
    run_id: str | None,
    motm_name: str,
    key_events: list[dict],
) -> int:
    """Apply bot match payouts. Returns coins earned."""
    existing = await fetch_match_reward_row(db, player_id, run_id=run_id) if run_id else None
    if existing and existing.get("xp_applied_at"):
        return int(existing.get("coins_earned") or 0)

    v2 = await economy_v2_enabled(db)
    coins = int(existing.get("coins_earned") or 0) if existing else 0

    if not existing:
        await sync_action_energy(db, player_id)
        coins = compute_bot_match_coins(result_str, division_win_coins, v2=v2)
        energy_cost = match_energy_cost("bot", v2=v2)
        await apply_match_economy(db, player_id, coins, energy_cost, "bot", run_id, result_str)

        user_lp = player_row.get("global_lp", 0)
        new_lp = max(0, user_lp + lp_change)

        await db.table("players").update({
            "league_points": player_row["league_points"] + points_earned,
            "global_lp": new_lp,
            "goal_difference": player_row["goal_difference"] + (goals_for - goals_against),
            "matches_played": player_row["matches_played"] + 1,
            "wins": player_row["wins"] + (1 if result_str == "win" else 0),
            "draws": player_row["draws"] + (1 if result_str == "draw" else 0),
            "losses": player_row["losses"] + (1 if result_str == "loss" else 0),
        }).eq("discord_id", player_id).execute()

        insert_res = await db.table("match_history").insert({
            "player_id": player_id,
            "result": result_str,
            "my_rating": team_rating,
            "opponent_rating": opponent_rating,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "coins_earned": coins,
            "points_earned": points_earned,
            "run_id": run_id,
        }).execute()
        history_id = (insert_res.data or [{}])[0]["id"]
    else:
        history_id = existing["id"]

    await apply_match_xp_if_needed(
        db,
        history_id=history_id,
        existing_row=existing,
        cards=cards,
        result_str=result_str,
        match_type="bot",
        motm_name=motm_name,
        key_events=key_events,
        club_name=club_name,
        team_rating=team_rating,
    )

    return coins


async def apply_friendly_human_rewards(
    db: Any,
    *,
    player_id: int,
    player_row: dict,
    result_str: str,
    cards: list[dict],
    club_name: str,
    team_rating: float,
    opponent_rating: float,
    goals_for: int,
    goals_against: int,
    run_id: str | None,
    motm_name: str,
    key_events: list[dict],
) -> int:
    """Apply friendly match payouts for one human manager. Returns coins earned."""
    existing = await fetch_match_reward_row(db, player_id, run_id=run_id) if run_id else None
    if existing and existing.get("xp_applied_at"):
        return int(existing.get("coins_earned") or 0)

    v2 = await economy_v2_enabled(db)
    coins = int(existing.get("coins_earned") or 0) if existing else 0

    if not existing:
        await sync_action_energy(db, player_id)
        coins = compute_friendly_match_coins(result_str, v2=v2)
        energy_cost = match_energy_cost("friendly", v2=v2)
        await apply_match_economy(db, player_id, coins, energy_cost, "friendly", run_id, result_str)

        await db.table("players").update({
            "matches_played": player_row["matches_played"] + 1,
            "wins": player_row["wins"] + (1 if result_str == "win" else 0),
            "draws": player_row["draws"] + (1 if result_str == "draw" else 0),
            "losses": player_row["losses"] + (1 if result_str == "loss" else 0),
        }).eq("discord_id", player_id).execute()

        insert_res = await db.table("match_history").insert({
            "player_id": player_id,
            "result": result_str,
            "my_rating": team_rating,
            "opponent_rating": opponent_rating,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "coins_earned": coins,
            "points_earned": 0,
            "run_id": run_id,
        }).execute()
        history_id = (insert_res.data or [{}])[0]["id"]
    else:
        history_id = existing["id"]

    await apply_match_xp_if_needed(
        db,
        history_id=history_id,
        existing_row=existing,
        cards=cards,
        result_str=result_str,
        match_type="friendly",
        motm_name=motm_name,
        key_events=key_events,
        club_name=club_name,
        team_rating=team_rating,
    )

    return coins
