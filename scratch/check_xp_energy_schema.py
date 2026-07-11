"""Check DEFINER + regen + run verify_required_schema.sql."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.prosecdef
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND p.proname = 'apply_card_xp'
              AND pg_get_function_identity_arguments(p.oid)
                  = 'p_card_id uuid, p_xp_amount integer, p_source text'
            """
        )
        print("prosecdef", cur.fetchone())
        cur.execute("SELECT value_json FROM game_config WHERE key = 'energy_regen_per_min'")
        print("regen", cur.fetchone())
        sql = (ROOT / "supabase/scripts/verify_required_schema.sql").read_text(encoding="utf-8")
        cur.execute(sql)
    conn.commit()
print("verify ok")
