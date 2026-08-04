"""Apply migration 097_academy_season_aging_decay.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "097_academy_season_aging_decay.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT pg_get_functiondef(p.oid)
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname='public' AND p.proname='process_season_aging'
            LIMIT 1
            """
        )
        body = cur.fetchone()[0]
        assert "academy_decayed" in body
    conn.commit()
print("Migration 097 applied — academy season POT decay wired.")
