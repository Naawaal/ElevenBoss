#!/usr/bin/env python3
"""Ops: resume all paused league seasons (037 / US-42.5).

Uses resume_season (rebase windows + status=active). Not a Discord command.

  python scratch/resume_paused_seasons.py
  python scratch/resume_paused_seasons.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("resume_paused_seasons")


async def _run(*, dry_run: bool) -> int:
    from apps.discord_bot.db.client import close_client, get_client
    from apps.discord_bot.core.league_lifecycle_engine import resume_season

    db = await get_client()
    res = await (
        db.table("league_seasons")
        .select(
            "id,league_id,status,pause_started_at,total_paused_seconds,"
            "current_matchday,season_number,pacing_mode"
        )
        .eq("status", "paused")
        .execute()
    )
    rows = res.data or []
    if not rows:
        logger.info("No paused seasons found.")
        await close_client()
        return 0

    for s in rows:
        league = await (
            db.table("leagues")
            .select("guild_id,name")
            .eq("id", s["league_id"])
            .maybe_single()
            .execute()
        )
        meta = league.data or {}
        logger.info(
            "paused season=%s guild=%s name=%r matchday=%s pause_started_at=%s",
            s["id"],
            meta.get("guild_id"),
            meta.get("name"),
            s.get("current_matchday"),
            s.get("pause_started_at"),
        )
        if dry_run:
            continue
        ok = await resume_season(db, s)
        logger.info("resume season=%s ok=%s", s["id"], ok)

    await close_client()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume paused league seasons")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not (
        os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")
    ):
        logger.error("SUPABASE_URL and SUPABASE_KEY required")
        return 2
    try:
        return asyncio.run(_run(dry_run=args.dry_run))
    except Exception:
        logger.exception("resume failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
