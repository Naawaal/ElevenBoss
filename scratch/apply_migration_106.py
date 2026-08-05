"""Apply migration 106_fix_ai_snapshot_positions.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "106_fix_ai_snapshot_positions.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT
                to_regprocedure('public.build_calibrated_pvp_ai_snapshot(numeric,text)') IS NOT NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"106 verify failed: {ok}"
    conn.commit()
print("Migration 106 applied — build_calibrated_pvp_ai_snapshot now generates valid position and name strings.")
