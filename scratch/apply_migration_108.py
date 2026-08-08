"""Apply migration 108_shelve_pvp_and_version_changelog.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "108_shelve_pvp_and_version_changelog.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT
                to_regprocedure('public.claim_deployment_changelog(text,text)') IS NOT NULL,
                to_regprocedure('public.complete_deployment_changelog(text,text,text,bigint)') IS NOT NULL,
                to_regprocedure('public.acquire_match_lock(bigint,text)') IS NOT NULL,
                to_regclass('public.pvp_matchmaking_queue') IS NULL,
                to_regclass('public.manager_rivalries') IS NULL,
                to_regprocedure('public.join_pvp_queue(bigint,bigint,bigint)') IS NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"108 verify failed: {ok}"
    conn.commit()
print("Migration 108 applied successfully.")
