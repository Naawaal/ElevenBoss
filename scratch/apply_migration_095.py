"""Apply migration 095_youth_academy_rarity_v2.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "095_youth_academy_rarity_v2.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute("SELECT public.academy_slot_cap(1), public.academy_slot_cap(5)")
        caps = cur.fetchone()
        cur.execute(
            """
            SELECT key, value_json
            FROM public.game_config
            WHERE key IN ('youth_intake_count', 'youth_academy_v2_enabled', 'academy_age_out')
            ORDER BY key
            """
        )
        cfg = cur.fetchall()
    conn.commit()
print(f"Migration 095 applied — slot caps L1/L5 = {caps}")
for key, val in cfg:
    print(f"  config {key}: {val}")
