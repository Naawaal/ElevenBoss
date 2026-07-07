"""Apply migration 037_audit_hardening.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/037_audit_hardening.sql"
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
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'match_history'
                  AND column_name IN ('run_id', 'xp_applied_at')
                ORDER BY column_name
                """
            )
            cols = {row[0] for row in cur.fetchall()}
            if cols != {"run_id", "xp_applied_at"}:
                print(f"Verification FAILED: match_history columns got {cols}", file=sys.stderr)
                return 1
            cur.execute(
                "SELECT public.formation_slot_role('4-4-2', 2), public.formation_slot_role('4-4-2', 10)"
            )
            role_def, role_fwd = cur.fetchone()
            if role_def != "DEF" or role_fwd != "FWD":
                print(
                    f"Verification FAILED: formation_slot_role returned {role_def}/{role_fwd}",
                    file=sys.stderr,
                )
                return 1
        if _VERIFY.exists():
            print(f"Running {_VERIFY.name}...")
            verify_sql = _VERIFY.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(verify_sql)
    print("Migration 037 applied — audit hardening verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
