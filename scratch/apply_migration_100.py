"""Apply migration 100_pvp_finalize_rpcs.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "100_pvp_finalize_rpcs.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT to_regprocedure('public.finalize_pvp_match(uuid,integer,integer,numeric,numeric)') IS NOT NULL,
                   to_regprocedure('public.finalize_ai_practice_match(uuid,bigint,text,integer,integer,numeric,numeric,boolean)') IS NOT NULL
            """
        )
        assert all(cur.fetchone())
    conn.commit()
print("Migration 100 applied — finalize_pvp_match + finalize_ai_practice_match.")
