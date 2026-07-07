"""Apply migration 025_player_level_system.sql via DATABASE_URL (psycopg)."""
from __future__ import annotations

import json
import os
import sys
import time

import psycopg
from dotenv import load_dotenv

load_dotenv()

_DEBUG_LOG = "debug-3c8a07.log"
_MIGRATION = "supabase/migrations/025_player_level_system.sql"


def _log(message: str, data: dict, hypothesis_id: str = "M") -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "3c8a07",
                        "runId": "migration-025",
                        "hypothesisId": hypothesis_id,
                        "timestamp": int(time.time() * 1000),
                        "location": "scratch/apply_migration_025.py",
                        "message": message,
                        "data": data,
                    }
                )
                + "\n"
            )
    except OSError:
        pass
    # #endregion


def _normalize_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found", file=sys.stderr)
        _log("missing DATABASE_URL", {})
        return 1

    if not os.path.exists(_MIGRATION):
        print(f"Missing {_MIGRATION}", file=sys.stderr)
        return 1

    sql = open(_MIGRATION, encoding="utf-8").read()
    dsn = _normalize_url(database_url)

    _log("connecting", {"migration": _MIGRATION})
    print(f"Executing {_MIGRATION} via psycopg...")

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                """
                SELECT
                    to_regprocedure('public.apply_card_xp(uuid,integer,text)') IS NOT NULL
                        AS has_apply_card_xp,
                    to_regprocedure('public.claim_pending_level_rewards(bigint)') IS NOT NULL
                        AS has_claim_rewards,
                    to_regclass('public.pending_level_rewards') IS NOT NULL
                        AS has_pending_table,
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'player_cards'
                          AND column_name = 'skill_points_earned'
                    ) AS has_earned_col
                """
            )
            row = cur.fetchone()
            verify = {
                "has_apply_card_xp": row[0],
                "has_claim_rewards": row[1],
                "has_pending_table": row[2],
                "has_earned_col": row[3],
            }
            _log("verification", verify, "V")

    if not all(verify.values()):
        print("Verification FAILED:", verify, file=sys.stderr)
        return 1

    print("Verification OK:", verify)
    print("Migration 025 applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
