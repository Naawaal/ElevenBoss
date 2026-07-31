# apps/discord_bot/core/potential_integrity.py
"""Anomaly monitor for rarity potential caps (049). No auto-repair."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def check_potential_integrity(db: Any, *, context: str) -> int:
    """Log CRITICAL if any potential integrity anomalies exist. Returns count."""
    try:
        res = await db.rpc("count_potential_integrity_anomalies").execute()
        raw = res.data
        count = int(raw if not isinstance(raw, list) else (raw[0] if raw else 0))
    except Exception:
        # 089 may not be applied yet — fall back to capped client sample
        try:
            sample = (
                await db.table("player_cards")
                .select("id,owner_id,rarity,overall,potential,base_potential")
                .limit(2000)
                .execute()
            )
            caps = {"Common": 75, "Rare": 85, "Epic": 92, "Legendary": 99}
            anomalies = []
            for row in sample.data or []:
                cap = caps.get(row.get("rarity") or "")
                pot = int(row.get("potential") or 0)
                base = row.get("base_potential")
                ovr = int(row.get("overall") or 0)
                if cap is None or pot > cap or ovr > pot or (
                    base is not None and int(base) > cap
                ):
                    anomalies.append(row)
            count = len(anomalies)
            if count:
                logger.critical(
                    "CRITICAL: potential_integrity_violation context=%s count=%s sample=%s",
                    context,
                    count,
                    anomalies[:5],
                )
                return count
            logger.info(
                "potential_integrity ok context=%s count=0 (sampled fallback)", context
            )
            return 0
        except Exception as exc:
            logger.error(
                "potential_integrity check failed context=%s: %s", context, exc, exc_info=True
            )
            return -1

    if count:
        logger.critical(
            "CRITICAL: potential_integrity_violation context=%s count=%s",
            context,
            count,
        )
    else:
        logger.info("potential_integrity ok context=%s count=0", context)
    return count
