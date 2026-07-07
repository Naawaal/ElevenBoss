# apps/discord_bot/core/economy_rpc.py
"""Economy v2 RPC helpers for Discord bot (US-25)."""
from __future__ import annotations

import logging
from typing import Any

from economy.flows import bot_match_coins, friendly_match_coins, league_match_coins_for_result

logger = logging.getLogger(__name__)

REGEN_PER_MIN = 1 / 6  # 1 energy per 6 minutes


def compute_bot_match_coins(result: str, division_win_coins: int, v2: bool = True) -> int:
    if not v2:
        if result == "win":
            return division_win_coins
        if result == "draw":
            return division_win_coins // 3
        return 15
    return bot_match_coins(result, division_win_coins)


def compute_league_match_coins(
    result: str,
    division: str,
    v2: bool = True,
    *,
    auto_sim: bool = False,
    auto_sim_mult: float | None = None,
) -> int:
    if not v2:
        if result == "win":
            return 150
        if result == "draw":
            return 50
        return 0
    # ponytail: auto_sim_mult override for tests; runtime reads game_config in league_rewards
    if auto_sim_mult is not None:
        from economy.flows import EconomyConfig, league_match_coins

        win_c = league_match_coins(division)
        if result == "win":
            base = win_c
        elif result == "draw":
            base = win_c // 3
        else:
            base = 0
        return int(base * auto_sim_mult) if auto_sim and base > 0 else base
    return league_match_coins_for_result(result, division, auto_sim=auto_sim)


def compute_friendly_match_coins(result: str, v2: bool = True) -> int:
    if not v2:
        return 0
    return friendly_match_coins(result)


def match_energy_cost(match_type: str, v2: bool = True) -> int:
    if not v2:
        return 10
    return {"bot": 20, "friendly": 15, "league": 10}.get(match_type, 20)


def minutes_to_full_action_energy(current: int, maximum: int = 100) -> int:
    if current >= maximum:
        return 0
    needed = maximum - current
    return int(needed / REGEN_PER_MIN)


def format_action_energy_status(current: int, maximum: int = 100) -> str:
    if current >= maximum:
        return f"⚡ **{current}/{maximum}** (Full)"
    mins = minutes_to_full_action_energy(current, maximum)
    hours, rem = divmod(mins, 60)
    return f"⚡ **{current}/{maximum}** (+{maximum - current} in {hours}h {rem}m)"


async def economy_v2_enabled(db: Any) -> bool:
    try:
        res = await db.rpc("get_game_config", {"p_key": "economy_v2_enabled"}).execute()
        val = res.data
        if val is True or val == "true":
            return True
        if isinstance(val, str):
            return val.strip('"') == "true"
    except Exception:
        logger.debug("economy_v2_enabled check failed — defaulting True", exc_info=True)
    return True


async def sync_action_energy(db: Any, club_id: int) -> dict:
    res = await db.rpc("sync_action_energy", {"p_club_id": club_id}).execute()
    return res.data or {}


async def apply_club_economy(
    db: Any,
    club_id: int,
    coin_delta: int,
    energy_delta: int,
    source: str,
    idempotency_key: str | None = None,
    meta: dict | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "p_club_id": club_id,
        "p_coin_delta": coin_delta,
        "p_energy_delta": energy_delta,
        "p_source": source,
        "p_idempotency_key": idempotency_key,
        "p_meta": meta or {},
    }
    res = await db.rpc("apply_club_economy", payload).execute()
    return res.data or {}


async def apply_match_economy(
    db: Any,
    club_id: int,
    coin_delta: int,
    energy_cost: int,
    match_type: str,
    run_id: str | None,
    result: str,
) -> dict:
    key = f"match:{run_id}:{club_id}" if run_id else None
    return await apply_club_economy(
        db,
        club_id,
        coin_delta,
        -energy_cost,
        f"match_{match_type}_{result}",
        key,
        {"match_type": match_type, "result": result, "run_id": run_id},
    )
