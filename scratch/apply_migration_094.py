"""Apply migration 094_manager_card_gifts.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "094_manager_card_gifts.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT gift_slot, COUNT(*)::int
            FROM public.manager_card_gifts
            WHERE campaign_id = 'manager_card_gifts_20260731'
            GROUP BY gift_slot
            ORDER BY gift_slot
            """
        )
        rows = cur.fetchall()
    conn.commit()
print("Migration 094 applied — manager card gifts installed.")
for slot, n in rows:
    print(f"  snapshot {slot}: {n}")
