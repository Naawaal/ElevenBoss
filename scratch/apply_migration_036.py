"""Apply migration 036_agent_sale_evo_status_guard.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/036_agent_sale_evo_status_guard.sql"


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
                "SELECT pg_get_functiondef("
                "'public.process_agent_sale(bigint, uuid)'::regprocedure)"
            )
            row = cur.fetchone()
            if not row or "status = 'active'" not in row[0]:
                print(
                    "Verification FAILED: process_agent_sale missing active evolution guard",
                    file=sys.stderr,
                )
                return 1
    print("Migration 036 applied — agent sale evolution guard aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
