"""Apply migration 028_economy_foundation.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

_MIGRATION = "supabase/migrations/028_economy_foundation.sql"


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found", file=sys.stderr)
        return 1

    if not os.path.exists(_MIGRATION):
        print(f"Missing {_MIGRATION}", file=sys.stderr)
        return 1

    sql = open(_MIGRATION, encoding="utf-8").read()
    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print(f"Executing {_MIGRATION} via psycopg...")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                """
                SELECT
                    to_regprocedure('public.apply_club_economy(bigint,bigint,integer,text,text,jsonb)') IS NOT NULL
                        AS has_apply,
                    to_regclass('public.game_config') IS NOT NULL AS has_config
                """
            )
            row = cur.fetchone()
            if not row or not all(row):
                print("Verification FAILED:", row, file=sys.stderr)
                return 1

    print("Migration 028 applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
