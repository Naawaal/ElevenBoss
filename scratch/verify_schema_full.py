"""Full US-23 schema + migration 026 verification against live DATABASE_URL."""
from __future__ import annotations

import json
import os
import sys
import time

import psycopg
from dotenv import load_dotenv

load_dotenv()

_DEBUG_LOG = "debug-3c8a07.log"

REQUIRED_TABLES = [
    "players",
    "player_cards",
    "active_evolutions",
    "active_training",
    "economy_ledger",
    "league_members",
    "match_locks",
    "match_runs",
    "pending_level_rewards",
    "fusion_daily_log",
    "player_drill_daily_log",
    "game_config",
    "agent_sale_daily_log",
    "energy_refill_daily_log",
]

REQUIRED_COLUMNS = [
    ("players", "training_energy"),
    ("players", "daily_drill_count"),
    ("players", "daily_drill_reset_at"),
    ("players", "last_evolution_started_at"),
    ("players", "action_energy"),
    ("players", "last_daily_login"),
    ("economy_ledger", "idempotency_key"),
    ("player_cards", "skill_points"),
    ("player_cards", "skill_points_earned"),
    ("player_cards", "skill_points_spent"),
    ("player_cards", "last_level_up_at"),
    ("player_cards", "xp"),
    ("player_cards", "level"),
    ("player_cards", "daily_alloc_count"),
    ("player_cards", "alloc_reset_date"),
]

REQUIRED_FUNCTIONS = [
    ("apply_card_xp", "uuid, integer, text"),
    ("claim_pending_level_rewards", "bigint"),
    ("level_from_xp", "integer"),
    ("cumulative_xp_for_level", "integer"),
    ("xp_needed_for_level", "integer"),
    ("process_match_result", "text, uuid[], integer, numeric[], integer[]"),
    ("process_stat_drill", "bigint, uuid, text"),
    ("train_with_fodder", "bigint, uuid, uuid"),
    ("allocate_skill_point", "bigint, uuid, text"),
    ("start_player_evolution", "bigint, uuid, text"),
    ("sync_training_energy", "bigint"),
    ("count_unclaimed_level_rewards", "bigint"),
    ("daily_match_xp_used", "uuid"),
    ("apply_club_economy", "bigint, bigint, integer, text, text, jsonb"),
    ("sync_action_energy", "bigint"),
    ("claim_daily_login", "bigint"),
    ("purchase_energy_refill", "bigint"),
    ("get_game_config", "text"),
]


def _log(message: str, data: dict) -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "3c8a07",
                        "runId": "schema-verify",
                        "hypothesisId": "DB",
                        "timestamp": int(time.time() * 1000),
                        "location": "scratch/verify_schema_full.py",
                        "message": message,
                        "data": data,
                    }
                )
                + "\n"
            )
    except OSError:
        pass
    # #endregion


def main() -> int:
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    missing_funcs: list[str] = []
    stats: dict = {}

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Tables
            for t in REQUIRED_TABLES:
                cur.execute("SELECT to_regclass(%s)", (f"public.{t}",))
                if cur.fetchone()[0] is None:
                    missing_tables.append(t)

            # Columns
            for table, col in REQUIRED_COLUMNS:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
                    """,
                    (table, col),
                )
                if cur.fetchone() is None:
                    missing_columns.append(f"{table}.{col}")

            # Functions
            for name, args in REQUIRED_FUNCTIONS:
                cur.execute(
                    "SELECT to_regprocedure(%s)",
                    (f"public.{name}({args})",),
                )
                if cur.fetchone()[0] is None:
                    missing_funcs.append(f"{name}({args})")

            # Run official verify script
            verify_ok = True
            verify_err = None
            try:
                with open("supabase/scripts/verify_required_schema.sql", encoding="utf-8") as f:
                    cur.execute(f.read())
                conn.commit()
            except Exception as e:
                verify_ok = False
                verify_err = str(e)
                conn.rollback()

            # US-23 stats
            cur.execute(
                "SELECT COUNT(*) FROM pending_level_rewards WHERE claimed = false"
            )
            stats["unclaimed_pending_rewards"] = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM player_cards
                WHERE level != public.level_from_xp(COALESCE(xp, 0))
                """
            )
            stats["cards_level_xp_mismatch"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM fusion_daily_log")
            stats["fusion_daily_log_rows"] = cur.fetchone()[0]

    report = {
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "missing_functions": missing_funcs,
        "verify_required_schema_ok": verify_ok,
        "verify_required_schema_error": verify_err,
        "stats": stats,
    }
    _log("schema_report", report)

    print("=== ElevenBoss Schema Verification ===\n")
    print(f"Tables missing ({len(missing_tables)}):", missing_tables or "none")
    print(f"Columns missing ({len(missing_columns)}):", missing_columns or "none")
    print(f"Functions missing ({len(missing_funcs)}):", missing_funcs or "none")
    print(f"verify_required_schema.sql:", "OK" if verify_ok else f"FAILED — {verify_err}")
    print("\nUS-23 stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    ok = not missing_tables and not missing_columns and not missing_funcs and verify_ok
    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
