# apps/discord_bot/core/display_cache.py
"""Short-TTL display caches — never authorize spends (050 US6 Tier 3–4)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from apps.discord_bot.core.cache import default_cache

STANDINGS_TTL_S = 30.0
LEADERBOARD_FIRST_TTL_S = 30.0
PROFILE_TTL_S = 20.0


def standings_key(season_id: str | int, division_tier: int | None = None) -> str:
    if division_tier is None:
        return f"season:{season_id}:standings"
    return f"season:{season_id}:standings:tier:{int(division_tier)}"


def leaderboard_first_key(
    scope: str, division: str | None = None, *, viewer_id: int | None = None
) -> str:
    if scope == "division" and division:
        base = f"division:{division}:lb:first"
    else:
        base = "global:lb:first"
    if viewer_id is not None:
        return f"{base}:v:{int(viewer_id)}"
    return base


def profile_key(owner_id: int) -> str:
    return f"player:{int(owner_id)}:profile"


async def get_or_set_standings(
    season_id: str | int,
    factory: Callable[[], Awaitable[Any]],
    *,
    division_tier: int | None = None,
    ttl_seconds: float = STANDINGS_TTL_S,
) -> Any:
    return await default_cache().get_or_set(
        standings_key(season_id, division_tier), ttl_seconds, factory
    )


def invalidate_standings(season_id: str | int, division_tier: int | None = None) -> None:
    cache = default_cache()
    if division_tier is not None:
        cache.delete(standings_key(season_id, division_tier))
    else:
        cache.delete_prefix(f"season:{season_id}:standings")


async def get_or_set_leaderboard_first(
    scope: str,
    factory: Callable[[], Awaitable[Any]],
    *,
    division: str | None = None,
    viewer_id: int | None = None,
    ttl_seconds: float = LEADERBOARD_FIRST_TTL_S,
) -> Any:
    return await default_cache().get_or_set(
        leaderboard_first_key(scope, division, viewer_id=viewer_id),
        ttl_seconds,
        factory,
    )


def invalidate_leaderboard_first(*, division: str | None = None) -> None:
    cache = default_cache()
    if division:
        cache.delete_prefix(f"division:{division}:lb:first")
    else:
        cache.delete_prefix("division:")
        cache.delete_prefix("global:lb:first")


async def get_or_set_profile_display(
    owner_id: int,
    factory: Callable[[], Awaitable[Any]],
    *,
    ttl_seconds: float = PROFILE_TTL_S,
) -> Any:
    return await default_cache().get_or_set(profile_key(owner_id), ttl_seconds, factory)


def invalidate_profile_display(owner_id: int) -> None:
    default_cache().delete(profile_key(owner_id))
