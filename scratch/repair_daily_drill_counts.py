"""Re-invoke repair_daily_drill_counts() (migration 058 already applied)."""
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

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT public.repair_daily_drill_counts()")
        print(json.dumps(cur.fetchone()[0], indent=2, default=str))
    conn.commit()
