# apps/discord_bot/core/identity_rpc.py
"""Thin Supabase wrappers for US-42.1 identity lifecycle RPCs."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def touch_club_activity(db: Any, club_id: int) -> dict:
    res = await db.rpc("touch_club_activity", {"p_club_id": club_id}).execute()
    return res.data or {}


async def classify_club_identity_status(db: Any, club_id: int) -> dict:
    res = await db.rpc("classify_club_identity_status", {"p_club_id": club_id}).execute()
    return res.data or {}


async def recover_club_identity(db: Any, club_id: int) -> dict:
    res = await db.rpc("recover_club_identity", {"p_club_id": club_id}).execute()
    return res.data or {}


async def touch_club_activity_best_effort(db: Any, club_id: int) -> None:
    """Bump activity after economy success; never raise into the caller."""
    try:
        await touch_club_activity(db, club_id)
    except Exception:
        logger.warning("touch_club_activity failed for club %s", club_id, exc_info=True)
