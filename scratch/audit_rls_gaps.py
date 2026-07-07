"""Find tables with RLS on but zero policies (same failure mode as league_members)."""
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
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                  AND c.relrowsecurity = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM pg_policies p
                      WHERE p.schemaname = 'public' AND p.tablename = c.relname
                  )
                ORDER BY c.relname
                """
            )
            orphans = [r[0] for r in cur.fetchall()]
            print("RLS_ON_NO_POLICIES:", orphans or "(none)")

            cur.execute(
                """
                SELECT c.relname, c.relrowsecurity,
                       (SELECT COUNT(*) FROM pg_policies p WHERE p.tablename = c.relname AND p.schemaname = 'public')
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                  AND c.relname IN (
                    'players', 'player_cards', 'league_members', 'league_participants',
                    'league_fixtures', 'league_seasons', 'match_locks', 'guild_config'
                  )
                ORDER BY c.relname
                """
            )
            print("KEY_TABLES:", cur.fetchall())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
