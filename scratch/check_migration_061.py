"""Check whether migration 061 objects exist on DATABASE_URL."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")
dsn = url.replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'players'
              AND column_name = 'intensity_tier'
            """
        )
        has_col = cur.fetchone() is not None
        cur.execute("SELECT to_regprocedure('public.backfill_tier_fatigue_rebalance()')")
        fn = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM players WHERE intensity_tier IS NULL")
        nulls = cur.fetchone()[0]
        cur.execute(
            "SELECT intensity_tier, COUNT(*) FROM players GROUP BY 1 ORDER BY 1"
        )
        dist = cur.fetchall()

print("intensity_tier column:", has_col)
print("backfill RPC:", fn)
print("null intensity_tier rows:", nulls)
print("tier distribution:", dist)
if has_col and fn:
    print("STATUS: MIGRATION_061_ALREADY_APPLIED — do not re-run unless on a different database")
else:
    print("STATUS: NEED_MIGRATION — run: python scratch/apply_migration_061.py")
