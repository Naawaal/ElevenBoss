"""Apply migration 101_pvp_rivalries_blocks_recovery.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "101_pvp_rivalries_blocks_recovery.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT to_regprocedure('public.set_pvp_block(bigint,bigint,boolean)') IS NOT NULL,
                   to_regprocedure('public.get_manager_rivalries(bigint)') IS NOT NULL,
                   to_regprocedure('public.get_rivalry_detail(bigint,bigint)') IS NOT NULL
            """
        )
        assert all(cur.fetchone())
    conn.commit()
print("Migration 101 applied — rivalries, blocks, recovery helpers.")
