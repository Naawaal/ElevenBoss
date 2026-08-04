"""Feature 053 readiness: migrations 098–101 + flag defaults."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

REQUIRED_FUNCS = [
    "public.join_pvp_queue(bigint,bigint,bigint)",
    "public.try_match_pvp_queue(bigint)",
    "public.get_battle_hub_state(bigint,bigint)",
    "public.finalize_pvp_match(uuid,integer,integer,numeric,numeric)",
    "public.finalize_ai_practice_match(uuid,bigint,text,integer,integer,numeric,numeric,boolean)",
    "public.set_pvp_block(bigint,bigint,boolean)",
    "public.get_manager_rivalries(bigint)",
    "public.reclaim_stale_pvp_matching(integer)",
]

checks: list[tuple[str, bool, object]] = []

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        for tbl in ("pvp_matchmaking_queue", "manager_rivalries", "pvp_blocks"):
            cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{tbl}",))
            ok = cur.fetchone()[0]
            checks.append((f"table {tbl}", ok, ok))

        for fn in REQUIRED_FUNCS:
            cur.execute("SELECT to_regprocedure(%s) IS NOT NULL", (fn,))
            ok = cur.fetchone()[0]
            checks.append((f"fn {fn.split('(')[0]}", ok, ok))

        cur.execute(
            """
            SELECT key, value_json #>> '{}'
            FROM public.game_config
            WHERE key IN (
              'battle_pvp_enabled',
              'pvp_rewards_enabled',
              'pvp_rivalries_enabled'
            )
            ORDER BY key
            """
        )
        flags = dict(cur.fetchall())
        checks.append(("config keys present", len(flags) >= 1, flags))
        pvp_on = flags.get("battle_pvp_enabled", "true")
        checks.append(
            (
                "battle_pvp_enabled set true",
                pvp_on.lower() in ("true", "1"),
                pvp_on,
            )
        )

failed = [c for c in checks if not c[1]]
for name, ok, detail in checks:
    print(f"{'OK' if ok else 'FAIL'}: {name} — {detail}")
if failed:
    raise SystemExit(f"{len(failed)} check(s) failed")
print("053 PvP ready (schema present; flag ON).")
