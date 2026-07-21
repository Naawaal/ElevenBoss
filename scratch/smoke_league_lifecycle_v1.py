"""Read-only smoke for League Lifecycle V1 (026)."""
from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


async def main() -> None:
    from leagues import assign_lifecycle_windows, lifecycle_v1_effective
    from leagues.cutover import can_start_v1_season

    print("=== Lifecycle V1 smoke (read-only) ===")
    print("effective(global=True, guild=None):", lifecycle_v1_effective(global_flag=True, guild_flag=None))
    print("can_start empty:", can_start_v1_season(effective_cutover=True, open_seasons=[]))

    windows = assign_lifecycle_windows(
        first_matchday_local_date=date(2026, 8, 1),
        timezone_name="Asia/Kathmandu",
        resolution_hour_local=20,
        matchday_count=14,
    )
    print(f"sample windows: {len(windows)} matchdays")
    print("  MD1 end UTC:", windows[0].window_end.isoformat())
    print("  MD14 end UTC:", windows[-1].window_end.isoformat())

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("No Supabase env — skipping DB read")
        return

    from supabase import create_client

    db = create_client(url, key)
    cfg = db.table("guild_config").select(
        "guild_id,league_timezone,league_resolution_hour_local,league_lifecycle_v1_enabled"
    ).limit(5).execute()
    print("guild_config sample rows:", len(cfg.data or []))
    seasons = (
        db.table("league_seasons")
        .select("id,status,pacing_mode,ruleset_version,timezone")
        .eq("pacing_mode", "lifecycle_v1")
        .limit(10)
        .execute()
    )
    print("open lifecycle_v1 seasons:", len(seasons.data or []))
    for s in seasons.data or []:
        print(" ", s)


if __name__ == "__main__":
    asyncio.run(main())
