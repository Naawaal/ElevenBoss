"""Apply migration 027_progression_hardening.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

_MIGRATION = "supabase/migrations/027_progression_hardening.sql"


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
                    to_regprocedure('public.count_unclaimed_level_rewards(bigint)') IS NOT NULL
                        AS has_count_rpc,
                    to_regclass('public.player_drill_daily_log') IS NOT NULL
                        AS has_drill_log
                """
            )
            row = cur.fetchone()
            if not row or not all(row):
                print("Verification FAILED:", row, file=sys.stderr)
                return 1

            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE NOT claimed) AS unclaimed,
                    COALESCE(SUM(missing_points) FILTER (WHERE NOT claimed), 0) AS unclaimed_pts
                FROM pending_level_rewards
                """
            )
            stats = cur.fetchone()
            print(f"Unclaimed rows: {stats[0]}, total points: {stats[1]}")

    print("Migration 027 applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
