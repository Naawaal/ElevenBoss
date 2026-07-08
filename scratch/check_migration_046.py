"""Check whether migration 046 rebalance values are already applied."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")

dsn = url.replace("postgresql+asyncpg://", "postgresql://")
keys = [
    "energy_regen_per_min",
    "match_energy_bot",
    "drill_basic_xp",
    "drill_advanced_xp",
    "evolution_cooldown_hours",
    "evolution_max_active",
]
expected = {
    "energy_regen_per_min": "0.25",
    "match_energy_bot": "15",
    "drill_basic_xp": "50",
    "drill_advanced_xp": "120",
    "evolution_cooldown_hours": "6",
    "evolution_max_active": "4",
}

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key, value_json::text FROM public.game_config WHERE key = ANY(%s) ORDER BY key",
            (keys,),
        )
        rows = dict(cur.fetchall())
        print("=== game_config ===")
        for k in keys:
            val = rows.get(k, "MISSING")
            ok = val == expected[k]
            print(f"{'OK' if ok else 'NEED'} {k}: {val} (want {expected[k]})")

        cur.execute(
            "SELECT pg_get_functiondef('public.start_player_evolution(bigint,uuid,text)'::regprocedure)"
        )
        fn = cur.fetchone()[0]
        print("\n=== start_player_evolution ===")
        print("evolution_cooldown_hours in RPC:", "evolution_cooldown_hours" in fn)
        print("evolution_max_active in RPC:", "evolution_max_active" in fn)
