"""Expire stale P2P transfer listings from the hourly scheduler."""
from __future__ import annotations

import logging

from apps.discord_bot.db.client import get_client

logger = logging.getLogger(__name__)


async def expire_stale_transfer_listings() -> int:
    """Run the atomic expiry RPC and return the number of released cards."""
    db = await get_client()
    result = await db.rpc("expire_stale_transfer_listings").execute()
    data = result.data or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    expired = int(data.get("expired_count", 0))
    logger.info("Transfer-listing expiry completed: expired_count=%s", expired)
    return expired
