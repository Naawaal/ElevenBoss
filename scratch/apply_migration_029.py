"""Apply migration 029_remove_live_pitch_config.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

_MIGRATION = "supabase/migrations/029_remove_live_pitch_config.sql"


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
                "SELECT COUNT(*) FROM public.game_config WHERE key = 'live_pitch_enabled'"
            )
            remaining = cur.fetchone()[0]
            if remaining:
                print("Verification FAILED: live_pitch_enabled still present", file=sys.stderr)
                return 1

    print("Migration 029 applied — live_pitch_enabled removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
