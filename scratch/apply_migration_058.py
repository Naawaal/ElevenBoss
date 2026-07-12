"""Apply migration 058 and run repair_daily_drill_counts once."""
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
sql_path = ROOT / "supabase" / "migrations" / "058_daily_drill_cap_desync.sql"

print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        print("Running repair_daily_drill_counts() ...")
        cur.execute("SELECT public.repair_daily_drill_counts()")
        row = cur.fetchone()
        print(json.dumps(row[0] if row else {}, indent=2, default=str))
    conn.commit()
print("Done.")
