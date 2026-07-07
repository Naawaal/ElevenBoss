# apps/discord_bot/core/league_rewards.py
"""League match reward application — economy v2, XP, career stats (US-26)."""
from __future__ import annotations

import logging
from typing import Any

from apps.discord_bot.core.economy_rpc import (
    apply_match_economy,
    compute_league_match_coins,
    economy_v2_enabled,
    match_energy_cost,
    sync_action_energy,
)
from apps.discord_bot.core.match_runs import fetch_match_reward_row
from apps.discord_bot.core.match_xp import apply_match_xp_if_needed

logger = logging.getLogger(__name__)


async def league_familiarity_multiplier(
    db: Any,
    *,
    season_id: str,
    discord_id: int,
    current_card_ids: list,
) -> float:
    """Compute lineup continuity rating multiplier from prior match_runs snapshots."""
    from leagues import familiarity_multiplier, xi_streak_including_current

    if len(current_card_ids) != 11:
        return 1.0
    current = frozenset(current_card_ids)
    try:
        fix_res = await db.table("league_fixtures").select("id, home_team_id, away_team_id, matchday").eq(
            "season_id", season_id
        ).eq("is_played", True).order("matchday").execute()
        fixture_ids = []
        for f in fix_res.data or []:
            if discord_id in (f["home_team_id"], f["away_team_id"]):
                fixture_ids.append(f["id"])
        if not fixture_ids:
            return familiarity_multiplier(1)
        runs_res = await db.table("match_runs").select("fixture_id, squad_snapshot").in_(
            "fixture_id", fixture_ids[-5:]
        ).execute()
        snap_by_fixture = {r["fixture_id"]: r.get("squad_snapshot") or {} for r in (runs_res.data or [])}
        history: list[frozenset] = []
        for fid in fixture_ids[-5:]:
            snap = snap_by_fixture.get(fid)
            if not snap:
                continue
            if snap.get("home_team_id") == discord_id:
                ids = snap.get("home_card_ids") or []
            elif snap.get("away_team_id") == discord_id:
                ids = snap.get("away_card_ids") or []
            else:
                continue
            if len(ids) == 11:
                history.append(frozenset(ids))
        streak = xi_streak_including_current(history, current)
        heavy_rotation = bool(history) and history[-1] != current
        return familiarity_multiplier(streak, heavy_rotation=heavy_rotation)
    except Exception:
        logger.debug("league_familiarity_multiplier failed", exc_info=True)
        return 1.0


async def _league_auto_sim_coin_mult(db: Any) -> float:
    try:
        res = await db.rpc("get_game_config", {"p_key": "league_auto_sim_coin_mult"}).execute()
        val = res.data
        if val is None:
            return 0.5
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val).strip('"'))
    except Exception:
        logger.debug("league_auto_sim_coin_mult read failed", exc_info=True)
        return 0.5


async def apply_league_human_rewards(
    db: Any,
    *,
    player_id: int,
    player_row: dict,
    result_str: str,
    fixture_id: str,
    run_id: str | None,
    cards: list[dict],
    club_name: str,
    team_rating: float,
    motm_name: str,
    key_events: list[dict],
    goals_for: int,
    goals_against: int,
    deduct_energy: bool,
) -> tuple[int, int]:
    """
    Apply league rewards for one human manager.
    Returns (coins_earned, season_pts) — season_pts for display only, not written to players.league_points.
    """
    existing = await fetch_match_reward_row(db, player_id, fixture_id=fixture_id)
    if existing and existing.get("xp_applied_at"):
        return int(existing.get("coins_earned") or 0), int(existing.get("points_earned") or 0)

    v2 = await economy_v2_enabled(db)
    division = player_row.get("division", "Grassroots")
    auto_sim = not deduct_energy
    if existing:
        coins = int(existing.get("coins_earned") or 0)
        season_pts = int(existing.get("points_earned") or 0)
        history_id = existing["id"]
    else:
        if v2 and auto_sim:
            mult = await _league_auto_sim_coin_mult(db)
            coins = compute_league_match_coins(
                result_str, division, v2=True, auto_sim=True, auto_sim_mult=mult
            )
        else:
            coins = compute_league_match_coins(result_str, division, v2=v2)
        season_pts = {"win": 3, "draw": 1, "loss": 0}[result_str]

        if deduct_energy and v2:
            await sync_action_energy(db, player_id)
            energy_cost = match_energy_cost("league", v2=True)
            econ = await apply_match_economy(db, player_id, coins, energy_cost, "league", run_id, result_str)
        elif v2:
            econ = await apply_match_economy(db, player_id, coins, 0, "league", run_id, result_str)
        else:
            econ = None
        # #region agent log
        try:
            import json, time
            with open("debug-93fd84.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({
                    "sessionId": "93fd84",
                    "timestamp": int(time.time() * 1000),
                    "location": "league_rewards.py:apply_league_human_rewards",
                    "message": "league_economy_applied",
                    "data": {
                        "player_id": player_id,
                        "coins": coins,
                        "result": result_str,
                        "auto_sim": auto_sim,
                        "deduct_energy": deduct_energy,
                        "econ": econ,
                    },
                    "hypothesisId": "E",
                    "runId": "pre-fix",
                }) + "\n")
        except Exception:
            pass
        # #endregion

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
            "opponent_rating": 0,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "coins_earned": coins,
            "points_earned": season_pts,
            "fixture_id": fixture_id,
            "run_id": run_id,
        }).execute()
        history_id = (insert_res.data or [{}])[0]["id"]

    await apply_match_xp_if_needed(
        db,
        history_id=history_id,
        existing_row=existing,
        cards=cards,
        result_str=result_str,
        match_type="league",
        motm_name=motm_name,
        key_events=key_events,
        club_name=club_name,
        team_rating=team_rating,
    )

    return coins, season_pts


async def check_matchday_milestone(
    db: Any,
    *,
    player_id: int,
    season_id: str,
    matchday: int,
    points_earned: int,
) -> int | None:
    """Grant bonus coins if matchday point threshold met. Returns bonus or None."""
    if points_earned <= 0:
        return None
    try:
        row_res = await db.table("league_matchday_milestones").select("*").eq(
            "season_id", season_id
        ).eq("player_id", player_id).eq("matchday", matchday).maybe_single().execute()
        row = row_res.data if row_res else None
        total_pts = (row["points_earned"] if row else 0) + points_earned
        claimed = row["milestone_claimed"] if row else False
        await db.table("league_matchday_milestones").upsert({
            "season_id": season_id,
            "player_id": player_id,
            "matchday": matchday,
            "points_earned": total_pts,
            "milestone_claimed": claimed,
        }).execute()
        if claimed:
            return None
        threshold_res = await db.rpc("get_game_config", {"p_key": "league_milestone_pts_threshold"}).execute()
        bonus_res = await db.rpc("get_game_config", {"p_key": "league_milestone_bonus_coins"}).execute()
        threshold = int(threshold_res.data or 6)
        bonus = int(bonus_res.data or 150)
        if total_pts >= threshold:
            from apps.discord_bot.core.economy_rpc import apply_club_economy
            key = f"league_milestone:{season_id}:{player_id}:{matchday}"
            await apply_club_economy(db, player_id, bonus, 0, "league_milestone", key, {"matchday": matchday})
            await db.table("league_matchday_milestones").update({"milestone_claimed": True}).eq(
                "season_id", season_id
            ).eq("player_id", player_id).eq("matchday", matchday).execute()
            return bonus
    except Exception:
        logger.debug("matchday milestone check failed", exc_info=True)
    return None
