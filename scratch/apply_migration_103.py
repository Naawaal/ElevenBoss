"""Apply migration 103_instant_pvp_backfill.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "103_instant_pvp_backfill.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT to_regprocedure('public.refresh_pvp_ghost_snapshot(bigint,uuid)') IS NOT NULL,
                   to_regprocedure('public.bootstrap_pvp_ghost_snapshots()') IS NOT NULL,
                   to_regprocedure('public.try_match_pvp_queue(bigint)') IS NOT NULL,
                   to_regprocedure('public.finalize_pvp_match(uuid,integer,integer,numeric,numeric)') IS NOT NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"103 verify failed: {ok}"
    conn.commit()
print("Migration 103 applied successfully — PvP backfill RPCs, tables, and guards ready.")
