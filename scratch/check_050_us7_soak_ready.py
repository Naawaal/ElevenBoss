"""Read-only: 050 schema presence + V3 flag/run snapshot for US7 soak gate."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

RPCS = (
    "get_division_leaderboard_page",
    "get_global_leaderboard_page",
    "browse_transfer_market",
    "get_development_hub_state",
    "get_skill_allocation_hub",
    "get_mentor_targets",
    "get_marketplace_hub_state",
)
IDX = (
    "idx_players_global_lp_human",
    "idx_players_division_lb_human",
    "idx_league_fixtures_season_played",
    "idx_players_division",
)

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT key, value_json::text
            FROM public.game_config
            WHERE key LIKE 'match_engine_v3%'
            ORDER BY 1
            """
        )
        print("=== V3 flags ===")
        for k, v in cur.fetchall():
            print(f"  {k} = {v}")

        cur.execute(
            """
            SELECT proname FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND proname = ANY(%s)
            ORDER BY 1
            """,
            (list(RPCS),),
        )
        found = {r[0] for r in cur.fetchall()}
        print("=== 050 RPCs ===")
        for name in RPCS:
            print(f"  [{'OK' if name in found else 'MISSING'}] {name}")

        cur.execute(
            "SELECT relname FROM pg_class WHERE relname = ANY(%s) ORDER BY 1",
            (list(IDX),),
        )
        found_i = {r[0] for r in cur.fetchall()}
        print("=== 091/092 indexes ===")
        for name in IDX:
            note = ""
            if name == "idx_players_division":
                note = " (should be ABSENT after 092)"
                ok = name not in found_i
            else:
                ok = name in found_i
            print(f"  [{'OK' if ok else 'BAD'}] {name}{note}")

        cur.execute(
            """
            SELECT run_type, engine_version, status, COUNT(*)::int
            FROM public.match_runs
            GROUP BY 1, 2, 3
            ORDER BY 1, 2, 3
            """
        )
        print("=== match_runs mix ===")
        for row in cur.fetchall():
            print(f"  {row}")
