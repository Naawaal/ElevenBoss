"""Apply migration 075_player_card_state_guards.sql via DATABASE_URL (psycopg)."""
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
sql_path = ROOT / "supabase" / "migrations" / "075_player_card_state_guards.sql"

if not sql_path.is_file():
    raise SystemExit(f"Missing migration file: {sql_path}")

print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
    conn.commit()
print("Migration 075 applied — assert_card_action_allowed + Critical/soft RPC wires.")
