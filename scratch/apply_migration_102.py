"""Apply migration 102_pvp_integrity_remediation.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "102_pvp_integrity_remediation.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT to_regprocedure('public.pvp_division_rank(integer)') IS NOT NULL,
                   to_regprocedure('public.build_pvp_squad_snapshot(bigint)') IS NOT NULL,
                   to_regprocedure('public.apply_pvp_match_xp_once(uuid,uuid,bigint,text,jsonb,numeric)') IS NOT NULL,
                   to_regprocedure('public.apply_pvp_post_match_fitness_once(uuid,uuid,bigint,jsonb,uuid[],jsonb)') IS NOT NULL,
                   to_regprocedure('public.complete_pvp_run(uuid)') IS NOT NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"102 verify failed: {ok}"
    conn.commit()
print("Migration 102 applied — PvP remediation RPCs and guards ready.")
