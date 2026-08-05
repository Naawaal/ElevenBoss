"""Apply migration 107_vote_reminders_and_changelog.sql via DATABASE_URL."""
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
sql_path = ROOT / "supabase" / "migrations" / "107_vote_reminders_and_changelog.sql"
print(f"Applying {sql_path.name} ...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"))
        cur.execute(
            """
            SELECT
                to_regprocedure('public.claim_due_topgg_vote_reminders(integer)') IS NOT NULL,
                to_regprocedure('public.claim_deployment_changelog(text,text)') IS NOT NULL,
                to_regprocedure('public.complete_deployment_changelog(text,text,text,bigint)') IS NOT NULL
            """
        )
        ok = cur.fetchone()
        assert all(ok), f"107 verify failed: {ok}"
    conn.commit()
print("Migration 107 applied successfully.")
