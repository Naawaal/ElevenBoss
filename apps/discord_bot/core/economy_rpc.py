# apps/discord_bot/core/economy_rpc.py
"""Economy v2 RPC helpers for Discord bot (US-25)."""
from __future__ import annotations

import logging
from typing import Any

from economy.flows import bot_match_coins, friendly_match_coins, league_match_coins_for_result

logger = logging.getLogger(__name__)

REGEN_PER_MIN = 0.25  # 1 energy per 4 minutes (game_config energy_regen_per_min / migration 046)


async def get_game_config_int(db: Any, key: str, default: int) -> int:
    """Fetch int config from game_config via RPC, with safe fallback."""
    try:
        res = await db.rpc("get_game_config_int", {"p_key": key, "p_default": int(default)}).execute()
        val = res.data
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            return int(val.strip('"'))
    except Exception:
        logger.debug("get_game_config_int(%s) failed — defaulting %s", key, default, exc_info=True)
    return int(default)


async def get_game_config_numeric(db: Any, key: str, default: float) -> float:
    """Fetch numeric config from game_config via RPC, with safe fallback."""
    try:
        res = await db.rpc("get_game_config_numeric", {"p_key": key, "p_default": float(default)}).execute()
        val = res.data
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return float(val.strip('"'))
    except Exception:
        logger.debug("get_game_config_numeric(%s) failed — defaulting %s", key, default, exc_info=True)
    return float(default)


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
        from economy.flows import league_match_coins

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


_MATCH_ENERGY_CONFIG_KEY = {
    "bot": "match_energy_bot",
    "league": "match_energy_league",
    "friendly": "match_energy_friendly",
}


async def get_match_energy_cost(db: Any, match_type: str, *, v2: bool = True) -> int:
    """Runtime match energy cost from game_config (single source for UI + deduction)."""
    fallback = match_energy_cost(match_type, v2=v2)
    key = _MATCH_ENERGY_CONFIG_KEY.get(match_type)
    if not key:
        return fallback
    return await get_game_config_int(db, key, fallback)


def minutes_to_full_action_energy(
    current: int,
    maximum: int = 100,
    *,
    regen_per_min: float | None = None,
) -> int:
    if current >= maximum:
        return 0
    rate = float(regen_per_min if regen_per_min is not None else REGEN_PER_MIN)
    if rate <= 0:
        rate = REGEN_PER_MIN
    needed = maximum - current
    return int(needed / rate)


def format_action_energy_status(
    current: int,
    maximum: int = 100,
    *,
    regen_per_min: float | None = None,
) -> str:
    if current >= maximum:
        return f"⚡ **{current}/{maximum}** (Full)"
    mins = minutes_to_full_action_energy(current, maximum, regen_per_min=regen_per_min)
    hours, rem = divmod(mins, 60)
    return f"⚡ **{current}/{maximum}** (+{maximum - current} in {hours}h {rem}m)"


async def format_action_energy_status_async(
    db: Any,
    current: int,
    maximum: int = 100,
) -> str:
    """Status line using live game_config.energy_regen_per_min when available."""
    rate = await get_game_config_numeric(db, "energy_regen_per_min", REGEN_PER_MIN)
    return format_action_energy_status(current, maximum, regen_per_min=rate)


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
