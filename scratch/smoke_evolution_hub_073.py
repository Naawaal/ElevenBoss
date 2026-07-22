"""Smoke-check get_evolution_hub_status after migration 073."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT key, value_json
            FROM game_config
            WHERE key IN (
                'evolution_cooldown_hours',
                'evolution_start_flat',
                'evolution_start_ovr_mult',
                'evolution_start_energy',
                'energy_max'
            )
            ORDER BY key
            """
        )
        print("config:", cur.fetchall())
        cur.execute(
            """
            SELECT discord_id, last_evolution_started_at,
                   EXTRACT(EPOCH FROM (NOW() - last_evolution_started_at))::INT AS ago_s
            FROM players
            WHERE last_evolution_started_at IS NOT NULL
            ORDER BY last_evolution_started_at DESC
            LIMIT 3
            """
        )
        rows = cur.fetchall()
        print("recent starters:", rows)
        if not rows:
            raise SystemExit("no clubs with last_evolution_started_at")
        oid = rows[0][0]
        ago = rows[0][2]
        cur.execute("SELECT public.get_evolution_hub_status(%s)", (oid,))
        status = cur.fetchone()[0]
        keys = [
            "cooldown_remaining_seconds",
            "can_start",
            "can_cold_start",
            "start_coin_flat",
            "start_coin_ovr_mult",
            "start_coin_multiplier",
            "start_energy_cost",
            "max_energy",
            "action_energy",
            "slots_label",
        ]
        print("owner", oid, "ago_s", ago, {k: status.get(k) for k in keys})
        rem = int(status.get("cooldown_remaining_seconds") or 0)
        # With 6h config, remaining + ago ≈ 6h (within a couple minutes)
        window = rem + int(ago or 0)
        print("remaining+ago seconds:", window, "expected ~21600 for 6h")
        assert status.get("start_coin_flat") == 500, status
        assert status.get("start_coin_ovr_mult") == 5, status
        assert status.get("start_coin_multiplier") == 5, status
        assert status.get("start_energy_cost") == 25, status
        if ago is not None and ago < 6 * 3600:
            assert rem > 0, "should still be on cooldown"
            assert window < 7 * 3600, f"looks like 10h clock still: {window}"
            assert window > 5 * 3600, f"cooldown window too short: {window}"
print("073 hub status smoke OK")
