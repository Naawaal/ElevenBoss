"""Apply migration 042_youth_intake.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/042_youth_intake.sql"
_VERIFY = Path(__file__).resolve().parents[1] / "supabase/scripts/verify_required_schema.sql"


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
        if _VERIFY.exists():
            print(f"Running {_VERIFY.name}...")
            verify_sql = _VERIFY.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(verify_sql)
    print("Migration 042 applied — youth intake.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
