"""Apply migration 033_league_economy_calibration.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/033_league_economy_calibration.sql"


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
                "WHERE table_schema = 'public' AND table_name = 'league_participants' "
                "AND column_name = 'entry_fee_paid'"
            )
            if not cur.fetchone():
                print("Verification FAILED: entry_fee_paid missing", file=sys.stderr)
                return 1
            cur.execute(
                "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' AND p.proname = 'charge_league_entry_fees'"
            )
            if not cur.fetchone():
                print("Verification FAILED: charge_league_entry_fees missing", file=sys.stderr)
                return 1
    print("Migration 033 applied — league economy calibration ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
