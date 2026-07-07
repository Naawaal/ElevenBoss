"""Apply migration 038_audit_hardening_followup.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/038_audit_hardening_followup.sql"
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
                SELECT to_regprocedure(proc)::text
                FROM (
                    VALUES
                        ('public.compute_card_ovr(text,integer,integer,integer,integer,integer,integer,integer,uuid)'),
                        ('public.peek_card_ovr(uuid,text,integer)'),
                        ('public.evolution_stat_reward_steps(uuid,text,integer)'),
                        ('public.apply_card_xp(uuid,integer,text)'),
                        ('public.apply_club_economy(bigint,bigint,integer,text,text,jsonb)'),
                        ('public.claim_evolution_reward(bigint,uuid)'),
                        ('public.start_player_evolution(bigint,uuid,text)')
                ) AS t(proc)
                WHERE to_regprocedure(proc) IS NULL
                """
            )
            missing = [row[0] for row in cur.fetchall()]
            if missing:
                print(f"Verification FAILED: missing procedures after 038", file=sys.stderr)
                return 1
        if _VERIFY.exists():
            print(f"Running {_VERIFY.name}...")
            verify_sql = _VERIFY.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(verify_sql)
    print("Migration 038 applied — audit hardening follow-up verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
