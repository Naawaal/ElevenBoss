# apps/discord_bot/core/pvp_rpc.py
"""Supabase RPC client wrapper functions for Ranked PvP matchmaking, ghost snapshots, and finalization (Feature 054)."""
from __future__ import annotations

import logging
from typing import Any

from supabase import AsyncClient

logger = logging.getLogger(__name__)


async def call_refresh_pvp_ghost_snapshot(
    client: AsyncClient,
    owner_id: int,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    """Call RPC refresh_pvp_ghost_snapshot to capture/refresh a manager's starting XI ghost snapshot."""
    try:
        res = await client.rpc(
            "refresh_pvp_ghost_snapshot",
            {"p_owner_id": owner_id, "p_source_run_id": source_run_id},
        ).execute()
        return res.data or {}
    except Exception as err:
        logger.error("Failed to refresh ghost snapshot for manager %s: %s", owner_id, err, exc_info=True)
        return {"success": False, "reason": str(err)}


async def call_try_match_pvp_queue(
    client: AsyncClient,
    guild_id: int | None = None,
) -> dict[str, Any]:
    """Call RPC try_match_pvp_queue to evaluate live humans, ghost snapshots, and AI backfill."""
    try:
        res = await client.rpc(
            "try_match_pvp_queue",
            {"p_guild_id": guild_id},
        ).execute()
        return res.data or {"matched": False, "reason": "empty_response"}
    except Exception as err:
        logger.error("Failed try_match_pvp_queue for guild %s: %s", guild_id, err, exc_info=True)
        return {"matched": False, "reason": str(err)}


async def call_finalize_pvp_match(
    client: AsyncClient,
    run_id: str,
    home_score: int,
    away_score: int,
    home_stats: dict[str, Any] | None = None,
    away_stats: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call RPC finalize_pvp_match to finalize live, ghost, or AI backfill matches with appropriate mode multipliers."""
    try:
        res = await client.rpc(
            "finalize_pvp_match",
            {
                "p_run_id": run_id,
                "p_home_score": home_score,
                "p_away_score": away_score,
                "p_home_stats": home_stats or {},
                "p_away_stats": away_stats or {},
                "p_events": events or [],
            },
        ).execute()
        return res.data or {}
    except Exception as err:
        logger.error("Failed finalize_pvp_match for run %s: %s", run_id, err, exc_info=True)
        return {"success": False, "reason": str(err)}
