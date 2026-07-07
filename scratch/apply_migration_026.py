"""Apply migration 026_match_xp_per_card.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

_MIGRATION = "supabase/migrations/026_match_xp_per_card.sql"


def _normalize_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found", file=sys.stderr)
        return 1

    if not os.path.exists(_MIGRATION):
        print(f"Missing {_MIGRATION}", file=sys.stderr)
        return 1

    sql = open(_MIGRATION, encoding="utf-8").read()
    dsn = _normalize_url(database_url)

    print(f"Executing {_MIGRATION} via psycopg...")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                """
                SELECT to_regprocedure(
                    'public.process_match_result(text,uuid[],integer,numeric[],integer[])'
                ) IS NOT NULL AS has_per_card_xp
                """
            )
            row = cur.fetchone()
            if not row or not row[0]:
                print("Verification FAILED: per-card process_match_result not found", file=sys.stderr)
                return 1

    print("Migration 026 applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
