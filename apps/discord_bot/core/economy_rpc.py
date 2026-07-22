# apps/discord_bot/core/economy_rpc.py
"""Economy v2 RPC helpers for Discord bot (US-25)."""
from __future__ import annotations

import json
import logging
from typing import Any

from economy.flows import bot_match_coins, friendly_match_coins, league_match_coins_for_result

from apps.discord_bot.core import config_cache, perf_signals

logger = logging.getLogger(__name__)

REGEN_PER_MIN = 0.25  # 1 energy per 4 minutes (game_config energy_regen_per_min / migration 046)

# Catalog: specs/038-db-scalability-performance/contracts/cache-policy-and-keys.md
PRICED_GAME_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "drill_basic_energy",
        "drill_advanced_energy",
        "drill_basic_xp",
        "drill_advanced_xp",
        "energy_refill_costs",
        "energy_refill_amount",
        "energy_regen_per_min",
        "energy_max",
        "daily_pack_cooldown_hours",
        "pack_standard_rarities",
        "pack_standard_rarity_weights",
        "fusion_coins",
        "wage_scale_factor",
        "wages_payroll_bill_scale",
    }
)


def invalidate_game_config(key: str | None = None) -> None:
    """Drop process-local cfg cache after a game_config write (US-43 FR-012 prep).

    Call from any path that mutates ``game_config``. Under multi-instance, TTL-only
    priced keys remain forbidden — wire shared/broadcast on top of this helper.
    """
    if key is None:
        config_cache.invalidate_prefix("cfg:")
        return
    # Stored as cfg:int:{key}:{default} / cfg:num:{key}:{default} / cfg:{key}
    config_cache.invalidate_prefix(f"cfg:int:{key}:")
    config_cache.invalidate_prefix(f"cfg:num:{key}:")
    config_cache.invalidate(config_cache.cache_key(key))


def invalidate_priced_game_config() -> None:
    """Invalidate all catalogued economy-priced tunables in this process."""
    for key in PRICED_GAME_CONFIG_KEYS:
        invalidate_game_config(key)


async def get_game_config_int(db: Any, key: str, default: int) -> int:
    """Fetch int config from game_config via RPC, with safe fallback + TTL cache."""
    ck = config_cache.cache_key(f"int:{key}:{default}")
    cached = config_cache.get(ck)
    if cached is not None:
        return int(cached)
    try:
        perf_signals.inc_round_trip()
        res = await db.rpc("get_game_config_int", {"p_key": key, "p_default": int(default)}).execute()
        val = res.data
        if isinstance(val, (int, float)):
            out = int(val)
        elif isinstance(val, str):
            out = int(val.strip('"'))
        else:
            out = int(default)
        config_cache.set(ck, out)
        return out
    except Exception:
        logger.debug("get_game_config_int(%s) failed — defaulting %s", key, default, exc_info=True)
    return int(default)


async def get_game_config_numeric(db: Any, key: str, default: float) -> float:
    """Fetch numeric config from game_config via RPC, with safe fallback + TTL cache."""
    ck = config_cache.cache_key(f"num:{key}:{default}")
    cached = config_cache.get(ck)
    if cached is not None:
        return float(cached)
    try:
        perf_signals.inc_round_trip()
        res = await db.rpc("get_game_config_numeric", {"p_key": key, "p_default": float(default)}).execute()
        val = res.data
        if isinstance(val, (int, float)):
            out = float(val)
        elif isinstance(val, str):
            out = float(val.strip('"'))
        else:
            out = float(default)
        config_cache.set(ck, out)
        return out
    except Exception:
        logger.debug("get_game_config_numeric(%s) failed — defaulting %s", key, default, exc_info=True)
    return float(default)


async def get_game_config_many(
    db: Any,
    specs: list[tuple[str, str, int | float]],
) -> dict[str, int | float]:
    """Batch-load int/numeric config keys in one RPC when possible (US-43).

    ``specs`` items: ``(key, kind, default)`` where kind is ``'int'`` or ``'num'``.
    Falls back to per-key helpers if ``get_game_config_many`` RPC is unavailable.
    """
    out: dict[str, int | float] = {}
    missing: list[tuple[str, str, int | float]] = []
    for key, kind, default in specs:
        prefix = "int" if kind == "int" else "num"
        ck = config_cache.cache_key(f"{prefix}:{key}:{default}")
        cached = config_cache.get(ck)
        if cached is not None:
            out[key] = int(cached) if kind == "int" else float(cached)
        else:
            missing.append((key, kind, default))
    if not missing:
        return out

    keys = [k for k, _, _ in missing]
    try:
        perf_signals.inc_round_trip()
        res = await db.rpc("get_game_config_many", {"p_keys": keys}).execute()
        raw = res.data
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise TypeError("unexpected get_game_config_many payload")
        for key, kind, default in missing:
            val = raw.get(key)
            if val is None:
                parsed: int | float = int(default) if kind == "int" else float(default)
            elif kind == "int":
                parsed = int(val) if not isinstance(val, str) else int(val.strip('"'))
            else:
                parsed = float(val) if not isinstance(val, str) else float(val.strip('"'))
            prefix = "int" if kind == "int" else "num"
            config_cache.set(config_cache.cache_key(f"{prefix}:{key}:{default}"), parsed)
            out[key] = parsed
        return out
    except Exception:
        logger.debug("get_game_config_many failed — per-key fallback", exc_info=True)

    for key, kind, default in missing:
        if kind == "int":
            out[key] = await get_game_config_int(db, key, int(default))
        else:
            out[key] = await get_game_config_numeric(db, key, float(default))
    return out


async def get_pack_rarity_override(db: Any) -> tuple[list[str], list[int]] | None:
    """Load standard pack rarity mix from game_config; None → use package defaults."""
    try:
        rarities_res = await db.rpc("get_game_config", {"p_key": "pack_standard_rarities"}).execute()
        weights_res = await db.rpc("get_game_config", {"p_key": "pack_standard_rarity_weights"}).execute()
        rarities_raw = rarities_res.data
        weights_raw = weights_res.data
        if isinstance(rarities_raw, str):
            rarities_raw = json.loads(rarities_raw)
        if isinstance(weights_raw, str):
            weights_raw = json.loads(weights_raw)
        if not isinstance(rarities_raw, list) or not isinstance(weights_raw, list):
            return None
        rarities = [str(r) for r in rarities_raw]
        weights = [int(w) for w in weights_raw]
        if len(rarities) != len(weights) or not rarities:
            return None
        return rarities, weights
    except Exception:
        logger.debug("get_pack_rarity_override failed — using package defaults", exc_info=True)
        return None


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
    maximum: int = 120,
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
    maximum: int = 120,
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
    maximum: int = 120,
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


async def wages_payroll_enabled(db: Any) -> bool:
    """Feature flag for weekly payroll (019). Default false."""
    try:
        res = await db.rpc("wages_payroll_enabled").execute()
        val = res.data
        if val is True or val is False:
            return bool(val)
        if isinstance(val, str):
            return val.strip().strip('"').lower() == "true"
    except Exception:
        logger.debug("wages_payroll_enabled check failed — defaulting False", exc_info=True)
    return False


async def league_dynamics_enabled(db: Any) -> bool:
    """Feature flag for League Dynamics (020). Default false."""
    try:
        res = await db.rpc("league_dynamics_enabled").execute()
        val = res.data
        if val is True or val is False:
            return bool(val)
        if isinstance(val, str):
            return val.strip().strip('"').lower() == "true"
    except Exception:
        try:
            res = await db.rpc("get_game_config", {"p_key": "league_dynamics_enabled"}).execute()
            val = res.data
            if val is True or val == "true":
                return True
            if isinstance(val, str):
                return val.strip().strip('"').lower() == "true"
        except Exception:
            logger.debug("league_dynamics_enabled check failed — defaulting False", exc_info=True)
    return False


async def league_automation_enabled(db: Any) -> bool:
    """Global feature flag for League Automation (021). Default false."""
    try:
        res = await db.rpc("league_automation_enabled").execute()
        val = res.data
        if val is True or val is False:
            return bool(val)
        if isinstance(val, str):
            return val.strip().strip('"').lower() == "true"
    except Exception:
        try:
            res = await db.rpc("get_game_config", {"p_key": "league_automation_enabled"}).execute()
            val = res.data
            if val is True or val == "true":
                return True
            if isinstance(val, str):
                return val.strip().strip('"').lower() == "true"
        except Exception:
            logger.debug("league_automation_enabled check failed — defaulting False", exc_info=True)
    return False


async def guild_automation_effective(db: Any, guild_id: int) -> bool:
    """Global on AND (guild NULL inherit OR guild true)."""
    from leagues import automation_effective

    global_on = await league_automation_enabled(db)
    if not global_on:
        return False
    try:
        res = await db.table("guild_config").select("league_automation_enabled").eq(
            "guild_id", guild_id
        ).maybe_single().execute()
        raw = (res.data or {}).get("league_automation_enabled") if res else None
        guild_flag: bool | None
        if raw is None:
            guild_flag = None
        else:
            guild_flag = bool(raw)
        return automation_effective(global_on, guild_flag)
    except Exception:
        logger.debug("guild_automation_effective failed guild=%s", guild_id, exc_info=True)
        return False


async def league_lifecycle_v1_enabled(db: Any) -> bool:
    """Global feature flag for League Lifecycle Rulebook V1 (026). Default false."""
    try:
        res = await db.rpc("league_lifecycle_v1_enabled").execute()
        val = res.data
        if val is True or val is False:
            return bool(val)
        if isinstance(val, str):
            return val.strip().strip('"').lower() == "true"
    except Exception:
        try:
            res = await db.rpc("get_game_config", {"p_key": "league_lifecycle_v1_enabled"}).execute()
            val = res.data
            if val is True or val == "true":
                return True
            if isinstance(val, str):
                return val.strip().strip('"').lower() == "true"
        except Exception:
            logger.debug("league_lifecycle_v1_enabled check failed — defaulting False", exc_info=True)
    return False


async def guild_lifecycle_v1_effective(db: Any, guild_id: int) -> bool:
    """Global on AND (guild NULL inherit OR guild true)."""
    from leagues import lifecycle_v1_effective

    global_on = await league_lifecycle_v1_enabled(db)
    if not global_on:
        return False
    try:
        res = await (
            db.table("guild_config")
            .select("league_lifecycle_v1_enabled")
            .eq("guild_id", guild_id)
            .maybe_single()
            .execute()
        )
        raw = (res.data or {}).get("league_lifecycle_v1_enabled") if res else None
        guild_flag: bool | None
        if raw is None:
            guild_flag = None
        else:
            guild_flag = bool(raw)
        return lifecycle_v1_effective(global_flag=global_on, guild_flag=guild_flag)
    except Exception:
        logger.debug("guild_lifecycle_v1_effective failed guild=%s", guild_id, exc_info=True)
        return False


async def fetch_payroll_strikes(db: Any, club_id: int) -> int:
    res = (
        await db.table("players")
        .select("payroll_strikes")
        .eq("discord_id", club_id)
        .maybe_single()
        .execute()
    )
    return int((res.data or {}).get("payroll_strikes") or 0)


async def wages_friendly_block_message(db: Any, club_id: int) -> str | None:
    """Return ephemeral copy when strikes block friendlies; else None."""
    from economy.wages import strike_blocks_friendly

    strikes = await fetch_payroll_strikes(db, club_id)
    threshold = await get_game_config_int(db, "payroll_strike_friendly_block", 2)
    if not strike_blocks_friendly(strikes, threshold=threshold):
        return None
    return (
        f"Payroll strikes (**{strikes}**) block **friendly** matches. "
        "Play league/bot matches and keep your Starting XI wage bill payable — "
        "check `/profile` → Finances."
    )


async def wages_market_block_message(db: Any, club_id: int) -> str | None:
    """Return ephemeral copy when strikes block P2P list / scouting; else None."""
    from economy.wages import strike_blocks_market

    strikes = await fetch_payroll_strikes(db, club_id)
    threshold = await get_game_config_int(db, "payroll_strike_market_block", 3)
    if not strike_blocks_market(strikes, threshold=threshold):
        return None
    return (
        f"Payroll strikes (**{strikes}**) block marketplace listings and youth scouting. "
        "Agent sales still work. Clear wage debt via `/profile` → Finances."
    )


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
    data = res.data or {}
    # US-42.1: best-effort activity touch — never roll back economy on failure
    from apps.discord_bot.core.identity_rpc import touch_club_activity_best_effort

    await touch_club_activity_best_effort(db, club_id)
    return data


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
