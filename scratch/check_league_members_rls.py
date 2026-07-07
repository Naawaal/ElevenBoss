"""One-off: inspect RLS on league_members."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found", file=sys.stderr)
        return 1

    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.relname, c.relrowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname IN ('league_members', 'match_locks', 'guild_config')
                ORDER BY c.relname
                """
            )
            print("RLS_STATUS:", cur.fetchall())
            cur.execute(
                """
                SELECT tablename, policyname, cmd, roles::text, qual, with_check
                FROM pg_policies
                WHERE schemaname = 'public' AND tablename = 'league_members'
                """
            )
            print("POLICIES:", cur.fetchall())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
