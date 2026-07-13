"""Apply migration 061 (tier fatigue rebalance) and run fair backfill RPC."""
from __future__ import annotations

import json
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
sql_path = ROOT / "supabase" / "migrations" / "061_tier_fatigue_rebalance.sql"

print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute("SELECT public.backfill_tier_fatigue_rebalance()")
        summary = cur.fetchone()[0]
    conn.commit()
print("Done.")
print("backfill_tier_fatigue_rebalance:", json.dumps(summary, default=str, indent=2))
