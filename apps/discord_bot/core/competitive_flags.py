# apps/discord_bot/core/competitive_flags.py
"""Competitive Bot Match feature flags (Feature 057). Default OFF."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def _parse_bool(raw: Any, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    text = str(raw).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    # jsonb may arrive as 'true' without quotes stripped already handled
    return default


async def is_competitive_match_enabled(db: Any | None = None) -> bool:
    """Env COMPETITIVE_MATCH_ENABLED overrides game_config; default false."""
    env = os.environ.get("COMPETITIVE_MATCH_ENABLED")
    if env is not None and str(env).strip() != "":
        return _parse_bool(env, False)

    if db is None:
        return False
    try:
        res = (
            await db.table("game_config")
            .select("value_json")
            .eq("key", "competitive_match_enabled")
            .maybe_single()
            .execute()
        )
        row = res.data if res else None
        if not row:
            return False
        return _parse_bool(row.get("value_json"), False)
    except Exception:
        logger.debug("competitive_match_enabled read failed — default false", exc_info=True)
        return False


async def competitive_et_multipliers(db: Any | None) -> tuple[float, float]:
    """Return (fatigue_mult, injury_mult) with defaults 1.35 / 1.25."""
    fatigue, injury = 1.35, 1.25
    if db is None:
        return fatigue, injury
    try:
        from apps.discord_bot.core.economy_rpc import get_game_config_numeric

        fatigue = await get_game_config_numeric(
            db, "competitive_extra_time_fatigue_multiplier", 1.35
        )
        injury = await get_game_config_numeric(
            db, "competitive_extra_time_injury_multiplier", 1.25
        )
    except Exception:
        logger.debug("competitive ET multipliers read failed", exc_info=True)
    return float(fatigue), float(injury)


async def bot_difficulty_settings(db: Any | None) -> dict[str, Any]:
    """Dynamic difficulty knobs for Bot Battle OVR offset."""
    out = {
        "enabled": True,
        "rating_offset": 0,
        "min_delta": -4,
        "max_delta": 4,
    }
    if db is None:
        return out
    try:
        from apps.discord_bot.core.economy_rpc import get_game_config_int, get_game_config_numeric

        res = (
            await db.table("game_config")
            .select("value_json")
            .eq("key", "bot_dynamic_difficulty_enabled")
            .maybe_single()
            .execute()
        )
        if res and res.data is not None:
            out["enabled"] = _parse_bool(res.data.get("value_json"), True)
        out["rating_offset"] = await get_game_config_int(db, "bot_difficulty_rating_offset", 0)
        out["min_delta"] = await get_game_config_int(db, "bot_difficulty_min_delta", -4)
        out["max_delta"] = await get_game_config_int(db, "bot_difficulty_max_delta", 4)
    except Exception:
        logger.debug("bot difficulty settings read failed", exc_info=True)
    return out


def apply_bot_difficulty_delta(
    base_rating: float,
    *,
    manager_ovr: float,
    settings: dict[str, Any],
) -> float:
    """Nudge bot OVR toward manager within min/max delta; offset from config."""
    if not settings.get("enabled", True):
        return float(base_rating) + float(settings.get("rating_offset") or 0)
    lo = int(settings.get("min_delta", -4))
    hi = int(settings.get("max_delta", 4))
    offset = int(settings.get("rating_offset") or 0)
    gap = float(manager_ovr) - float(base_rating)
    # Move bot toward manager by clamped gap fraction
    nudge = max(lo, min(hi, int(round(gap * 0.35)) + offset))
    return max(1.0, min(99.0, float(base_rating) + nudge))
