"""Weekly payroll batch from the Monday scheduler (019)."""
from __future__ import annotations

import logging

from apps.discord_bot.db.client import get_client

logger = logging.getLogger(__name__)


async def run_weekly_payroll() -> dict:
    """Call process_weekly_payroll; returns RPC summary dict."""
    db = await get_client()
    result = await db.rpc("process_weekly_payroll").execute()
    data = result.data or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    logger.info(
        "Weekly payroll completed: processed=%s skipped=%s week_key=%s reason=%s",
        data.get("processed"),
        data.get("skipped"),
        data.get("week_key"),
        data.get("reason"),
    )
    return data if isinstance(data, dict) else {}
