# apps/discord_bot/tasks/pvp_matchmaker_job.py
"""APScheduler job: expire PvP queue rows, recover runs, attempt matches (Feature 053)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def pvp_matchmaker_job(bot: Any) -> None:
    """Interval matchmaker — safe no-op when flag off / no searchers."""
    try:
        from apps.discord_bot.db.client import get_client
        from apps.discord_bot.core.pvp_match import (
            dispatch_matched_pvp,
            recover_active_pvp_runs,
            retry_completing_pvp_runs,
        )
        from apps.discord_bot.core.match_runs import reconcile_orphaned_match_locks

        db = await get_client()
        expired = 0
        reclaimed = 0
        matched = 0
        recovered = 0
        completing = 0

        try:
            res = await db.rpc("expire_pvp_queue_rows", {}).execute()
            expired = int(res.data or 0) if isinstance(res.data, int) else 0
        except Exception:
            logger.debug("expire_pvp_queue_rows failed", exc_info=True)

        try:
            res = await db.rpc("reclaim_stale_pvp_matching", {"p_stale_seconds": 120}).execute()
            reclaimed = int(res.data or 0) if isinstance(res.data, int) else 0
        except Exception:
            logger.debug("reclaim_stale_pvp_matching failed", exc_info=True)

        try:
            orphans = await reconcile_orphaned_match_locks(db)
            if orphans:
                logger.info("pvp_matchmaker orphan_locks_cleared=%s", orphans)
        except Exception:
            logger.debug("reconcile_orphaned_match_locks failed", exc_info=True)

        try:
            recovered = await recover_active_pvp_runs(bot, db)
        except Exception:
            logger.debug("recover_active_pvp_runs failed", exc_info=True)

        try:
            completing = await retry_completing_pvp_runs(db)
        except Exception:
            logger.debug("retry_completing_pvp_runs failed", exc_info=True)

        for _ in range(3):
            try:
                res = await db.rpc("try_match_pvp_queue", {"p_guild_id": None}).execute()
                data = res.data if isinstance(res.data, dict) else {}
                if not data.get("matched"):
                    break
                matched += 1
                logger.info(
                    "pvp_match_found run=%s home=%s away=%s guild=%s",
                    data.get("run_id"),
                    data.get("home_owner_id"),
                    data.get("away_owner_id"),
                    data.get("guild_id"),
                )
                asyncio.create_task(dispatch_matched_pvp(bot, data))
            except Exception:
                logger.debug("try_match_pvp_queue failed", exc_info=True)
                break

        if expired or reclaimed or matched or recovered or completing:
            logger.info(
                "pvp_matchmaker metrics expired=%s reclaimed=%s matched=%s recovered=%s completing_retry=%s",
                expired,
                reclaimed,
                matched,
                recovered,
                completing,
            )
    except Exception:
        logger.exception("pvp_matchmaker_job crashed")
