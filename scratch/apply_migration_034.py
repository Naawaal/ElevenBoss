"""Apply migration 034_league_season_threads.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/034_league_season_threads.sql"


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1
    if not _MIGRATION.exists():
        print(f"Missing {_MIGRATION}", file=sys.stderr)
        return 1
    import psycopg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    sql = _MIGRATION.read_text(encoding="utf-8")
    print(f"Executing {_MIGRATION.name} via psycopg...")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'league_seasons' "
                "AND column_name = 'journal_thread_id'"
            )
            if not cur.fetchone():
                print("Verification FAILED: journal_thread_id missing", file=sys.stderr)
                return 1
    print("Migration 034 applied — league season thread columns ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
