"""Quick readiness check: 083 V3 flags + 086 marketplace objects."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

checks: list[tuple[str, bool, object]] = []

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT key, value_json::text
            FROM public.game_config
            WHERE key IN (
              'match_engine_v3_bot',
              'match_engine_v3_league',
              'match_engine_v3_friendly'
            )
            ORDER BY key
            """
        )
        flags = dict(cur.fetchall())
        checks.append(
            (
                "083 V3 flags present",
                set(flags)
                == {
                    "match_engine_v3_bot",
                    "match_engine_v3_league",
                    "match_engine_v3_friendly",
                },
                flags,
            )
        )

        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='public' AND table_name='match_runs'
              AND column_name='engine_version'
            """
        )
        checks.append(("083 match_runs.engine_version", cur.fetchone()[0] == 1, None))

        cur.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='public' AND table_name='transfer_sales_log'
              AND column_name='fair_value_coins'
            """
        )
        checks.append(("086 transfer_sales_log.fair_value_coins", cur.fetchone()[0] == 1, None))

        cur.execute("SELECT to_regclass('public.card_ownership_history') IS NOT NULL")
        checks.append(("086 card_ownership_history", bool(cur.fetchone()[0]), None))

        for name in (
            "get_price_discovery",
            "get_market_analytics",
            "ensure_card_ownership_open",
            "get_card_ownership_history",
        ):
            cur.execute(
                """
                SELECT COUNT(*) FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = %s
                """,
                (name,),
            )
            checks.append((f"086 fn {name}", cur.fetchone()[0] >= 1, None))

print("DB readiness")
all_ok = True
for name, ok, detail in checks:
    mark = "OK" if ok else "MISSING"
    if not ok:
        all_ok = False
    extra = f"  {detail}" if detail is not None else ""
    print(f"  [{mark}] {name}{extra}")
print("OVERALL:", "READY" if all_ok else "NEEDS MIGRATION")
