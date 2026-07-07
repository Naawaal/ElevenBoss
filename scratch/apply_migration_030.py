"""Apply migration 030_league_members_rls.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

_MIGRATION = "supabase/migrations/030_league_members_rls.sql"


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
                SELECT policyname, cmd
                FROM pg_policies
                WHERE schemaname = 'public' AND tablename = 'league_members'
                ORDER BY policyname
                """
            )
            policies = cur.fetchall()
            if len(policies) < 2:
                print("Verification FAILED: expected 2 league_members policies", file=sys.stderr)
                print(policies, file=sys.stderr)
                return 1
            print("Policies:", policies)

    print("Migration 030 applied — league_members RLS policies created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
