"""Best-effort Medical Update DMs for 016 tier-fatigue early discharges.

Usage (pipe early_discharged array from apply_migration_061 output):
  python scratch/notify_tier_fatigue_backfill.py --from-file early.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

logger = logging.getLogger("notify_tier_fatigue_backfill")


def _load_entries(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.from_file:
        raw = Path(args.from_file).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    data = json.loads(raw or "[]")
    if isinstance(data, dict) and "early_discharged" in data:
        data = data["early_discharged"]
    if not isinstance(data, list):
        raise SystemExit("Expected a JSON array (or backfill summary with early_discharged)")
    return [e for e in data if isinstance(e, dict)]


def _message_for(names: list[str]) -> str:
    joined = ", ".join(names)
    return (
        f"🏥 **Medical Update:** {joined} "
        f"{'have' if len(names) > 1 else 'has'} been discharged early "
        "under updated league-intensity medical protocols.\n"
        "Check `/store` → Facilities → Hospital or `/profile` for status."
    )


async def _send_dms(entries: list[dict[str, Any]]) -> None:
    token = os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN (or BOT_TOKEN) not set in .env")

    import discord

    by_owner: dict[int, list[str]] = defaultdict(list)
    for e in entries:
        try:
            oid = int(e.get("owner_id"))
        except (TypeError, ValueError):
            continue
        name = str(e.get("name") or "Player").strip() or "Player"
        by_owner[oid].append(name)

    if not by_owner:
        print("No valid owner_ids to notify.")
        return

    intents = discord.Intents.none()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        try:
            for owner_id, names in by_owner.items():
                seen: set[str] = set()
                uniq = [n for n in names if not (n in seen or seen.add(n))]
                try:
                    user = await client.fetch_user(owner_id)
                    await user.send(_message_for(uniq))
                    print(f"DM ok → {owner_id} ({len(uniq)} player(s))")
                except Exception as exc:  # noqa: BLE001
                    logger.info("DM failed for %s: %s", owner_id, exc)
                    print(f"DM failed → {owner_id}: {exc}")
        finally:
            await client.close()

    await client.start(token)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-file", type=str, default=None)
    args = parser.parse_args()
    entries = _load_entries(args)
    if not entries:
        print("No early_discharged entries.")
        return
    asyncio.run(_send_dms(entries))


if __name__ == "__main__":
    main()
