"""Apply migration 105_fix_complete_pvp_run_ghost_ai.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "105_fix_complete_pvp_run_ghost_ai.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT
                to_regprocedure('public.complete_pvp_run(uuid)') IS NOT NULL,
                to_regprocedure('public.pvp_daily_ghost_refresh()') IS NOT NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"105 verify failed: {ok}"
    conn.commit()
print("Migration 105 applied — complete_pvp_run now handles ghost/AI modes correctly.")
