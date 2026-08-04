"""Apply migration 098_pvp_matchmaking_rivalries.sql via DATABASE_URL."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set in .env")
dsn = url.replace("postgresql+asyncpg://", "postgresql://")
sql_path = ROOT / "supabase" / "migrations" / "098_pvp_matchmaking_rivalries.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT to_regclass('public.pvp_matchmaking_queue') IS NOT NULL,
                   to_regclass('public.manager_rivalries') IS NOT NULL,
                   to_regclass('public.pvp_blocks') IS NOT NULL,
                   to_regprocedure('public.join_pvp_queue(bigint,bigint,bigint)') IS NOT NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"098 verify failed: {ok}"
        cur.execute(
            "SELECT value_json #>> '{}' FROM public.game_config WHERE key = 'battle_pvp_enabled'"
        )
        flag = cur.fetchone()[0]
        assert flag == "false", f"expected battle_pvp_enabled=false, got {flag!r}"
    conn.commit()
print("Migration 098 applied — PvP schema spine ready (flag OFF).")
