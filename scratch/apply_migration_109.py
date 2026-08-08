"""Apply migration 109_competitive_bot_match.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "109_competitive_bot_match.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT
                to_regclass('public.player_suspensions') IS NOT NULL,
                EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'match_runs'
                      AND column_name = 'competitive_state'
                ),
                EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'match_history'
                      AND column_name = 'decided_by'
                ),
                to_regprocedure('public.list_active_suspensions(bigint)') IS NOT NULL,
                to_regprocedure('public.apply_bot_match_discipline(uuid,bigint,jsonb)') IS NOT NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"109 verify failed: {ok}"
    conn.commit()
print("Migration 109 applied successfully.")
