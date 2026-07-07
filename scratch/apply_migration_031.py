"""Apply migration 031_rls_policy_guard.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

_MIGRATION = "supabase/migrations/031_rls_policy_guard.sql"


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

    print("Migration 031 applied — RLS policy guard active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
