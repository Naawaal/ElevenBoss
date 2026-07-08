"""Apply migration 045_fix_age_xp_multiplier.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/045_fix_age_xp_multiplier.sql"
_VERIFY = Path(__file__).resolve().parents[1] / "supabase/scripts/verify_required_schema.sql"


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1
    import psycopg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    sql = _MIGRATION.read_text(encoding="utf-8")
    print(f"Executing {_MIGRATION.name} via psycopg...")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        if _VERIFY.exists():
            print("Running verify script...")
            with conn.cursor() as cur:
                cur.execute(_VERIFY.read_text(encoding="utf-8"))
    print("Migration 045 applied — age XP multiplier fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
