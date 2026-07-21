#!/usr/bin/env python3
"""Operator-only League Lifecycle V1 recovery (027).

Trusted host with DATABASE_URL / Supabase service credentials. Not a Discord command.

Usage:
  python scripts/league_lifecycle_recover.py
  python scripts/league_lifecycle_recover.py --guild-id 1234567890

Steps (same paths as automation):
  1. recover_stalled_operations
  2. process_due_transitions (trigger=operator_recover when journaling)
  3. publish_pending_outbox

Never edits standings/rewards directly or converts a living season ruleset.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("league_lifecycle_recover")


async def _run(*, guild_id: int | None) -> int:
    from apps.discord_bot.db.client import get_client
    from apps.discord_bot.core.league_lifecycle_engine import process_due_transitions
    from apps.discord_bot.core.league_outbox import publish_pending_outbox
    from apps.discord_bot.core.league_recovery import recover_stalled_operations

    # Minimal bot stub — engine/outbox only need db for competitive work; outbox
    # publish may no-op Discord sends without a live client.
    class _BotStub:
        def get_guild(self, _gid: int):  # noqa: ANN001
            return None

    bot = _BotStub()
    db = await get_client()
    now = datetime.now(timezone.utc)

    stalled = await recover_stalled_operations(db)
    logger.info("stalled_ops_cleared=%s", stalled)

    # ponytail: guild filter is best-effort via season list after due pass;
    # full multi-guild wake matches automation. Upgrade: pass guild scope into engine.
    if guild_id is not None:
        logger.info("guild_id=%s requested — running full due pass (engine scopes by V1 seasons)", guild_id)

    counts = await process_due_transitions(bot, db, now)
    logger.info("process_due_transitions=%s", counts)

    published = await publish_pending_outbox(bot, db)
    logger.info("outbox_publish=%s", published)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry League Lifecycle V1 via shared engine")
    parser.add_argument("--guild-id", type=int, default=None, help="Optional Discord guild id (logged; wake still evaluates all V1 seasons)")
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL") and not (
        os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")
    ):
        logger.error("DATABASE_URL or SUPABASE_URL+SUPABASE_KEY required")
        return 2

    try:
        return asyncio.run(_run(guild_id=args.guild_id))
    except Exception:
        logger.exception("operator recovery failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
