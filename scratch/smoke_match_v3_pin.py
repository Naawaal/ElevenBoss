"""Live DB pin smoke for 044 — proves new kicks honor game_config flags (no Discord).

Creates then abandons ephemeral bot + friendly runs via create_ephemeral_run.
Does NOT inflate completed soak counts.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> None:
    from apps.discord_bot.core.config_cache import invalidate_prefix
    from apps.discord_bot.core.match_runs import (
        ENGINE_NSS_V2,
        ENGINE_NSS_V3,
        abandon_run,
        create_ephemeral_run,
        generate_sim_seed,
        resolve_engine_version,
    )
    from apps.discord_bot.db.client import close_client, get_client

    # Bust process-local cache so we see SQL flag flips immediately
    invalidate_prefix("cfg:")

    db = await get_client()
    bot_ev, bot_ssv = await resolve_engine_version(db, "bot")
    league_ev, _ = await resolve_engine_version(db, "league")
    friendly_ev, _ = await resolve_engine_version(db, "friendly")
    print(f"resolve bot={bot_ev}/{bot_ssv} league={league_ev} friendly={friendly_ev}")
    assert bot_ev == ENGINE_NSS_V3, f"expected bot nss_v3, got {bot_ev}"
    assert league_ev == ENGINE_NSS_V2
    assert friendly_ev == ENGINE_NSS_V2

    players = (
        await db.table("players")
        .select("discord_id")
        .eq("is_ai", False)
        .limit(2)
        .execute()
    )
    rows = players.data or []
    if not rows:
        raise SystemExit("No human players in DB for FK smoke")
    home_id = int(rows[0]["discord_id"])
    away_id = int(rows[1]["discord_id"]) if len(rows) > 1 else home_id

    seed = generate_sim_seed()
    bot_row = await create_ephemeral_run(
        db,
        run_type="bot",
        active_discord_id=home_id,
        home_discord_id=home_id,
        away_discord_id=None,
        sim_seed=seed,
        guild_id=None,
        thread_id=None,
        squad_snapshot={"smoke": "044_pin"},
    )
    bot_id = bot_row["id"]
    assert bot_row.get("engine_version") == ENGINE_NSS_V3, bot_row
    print(f"bot run pinned {bot_row['engine_version']} id={bot_id}")

    friendly_row = await create_ephemeral_run(
        db,
        run_type="friendly",
        active_discord_id=home_id,
        home_discord_id=home_id,
        away_discord_id=away_id,
        sim_seed=seed ^ 1,
        guild_id=None,
        thread_id=None,
        squad_snapshot={"smoke": "044_friendly_pin"},
    )
    friendly_id = friendly_row["id"]
    assert friendly_row.get("engine_version") == ENGINE_NSS_V2, friendly_row
    print(f"friendly run pinned {friendly_row['engine_version']} id={friendly_id}")

    await abandon_run(db, bot_id, reason="044_pin_smoke")
    await abandon_run(db, friendly_id, reason="044_pin_smoke")
    print("abandoned smoke runs OK")
    await close_client()
    print("smoke_match_v3_pin OK")


if __name__ == "__main__":
    asyncio.run(main())
