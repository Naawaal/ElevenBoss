"""Smoke 048: settle Season #2 MD5 pending fixtures via settle_expired_fixture.

Safe settle-once: already-played fixtures no-op.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "leagues"))
sys.path.insert(0, str(ROOT / "apps"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

SEASON_ID = "eea8660e-7e50-461d-b9ce-78f8299b96fc"
# Known MD5 pending pair (may already be settled)
TARGET_IDS = (
    "d641b016-b36b-4fb9-86c0-6c66981b70ce",
    "c8f1eb10-aafc-43f0-96b2-2a733fe4ff26",
)


async def main() -> None:
    from apps.discord_bot.db.client import get_client
    from apps.discord_bot.core.league_expired_settle import settle_expired_fixture

    db = await get_client()
    res = await (
        db.table("league_fixtures")
        .select(
            "id,is_played,home_score,away_score,result_type,resolved_by,window_end,"
            "home_team_id,away_team_id,season_id,"
            "home:players!league_fixtures_home_team_id_fkey(*), "
            "away:players!league_fixtures_away_team_id_fkey(*)"
        )
        .eq("season_id", SEASON_ID)
        .eq("matchday", 5)
        .execute()
    )
    rows = res.data or []
    print(f"MD5 fixtures: {len(rows)}")
    for f in rows:
        print(
            f"  {f['id'][:8]}… played={f['is_played']} "
            f"{f.get('home_score')}-{f.get('away_score')} "
            f"rt={f.get('result_type')} by={f.get('resolved_by')}"
        )

    pending = [f for f in rows if not f["is_played"] and f["id"] in TARGET_IDS]
    if not pending:
        pending = [f for f in rows if not f["is_played"]]
    if not pending:
        print("OK: no unplayed MD5 fixtures (already settled)")
        return

    class _Bot:
        pass

    class _Guild:
        id = 0

    for f in pending:
        ok = await settle_expired_fixture(
            _Bot(), db, _Guild(), f, season_threads=None, silent=True
        )
        print(f"settle {f['id'][:8]}… → {ok}")

    after = await (
        db.table("league_fixtures")
        .select("id,is_played,home_score,away_score,result_type,resolved_by")
        .eq("season_id", SEASON_ID)
        .eq("matchday", 5)
        .execute()
    )
    for f in after.data or []:
        print(
            f"  AFTER {f['id'][:8]}… played={f['is_played']} "
            f"{f.get('home_score')}-{f.get('away_score')} "
            f"rt={f.get('result_type')} by={f.get('resolved_by')}"
        )


if __name__ == "__main__":
    asyncio.run(main())
