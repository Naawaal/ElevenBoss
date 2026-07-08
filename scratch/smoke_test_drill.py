"""Smoke-test process_stat_drill after migration 045."""
from __future__ import annotations

import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pc.id, pc.owner_id
            FROM player_cards pc
            JOIN players p ON p.discord_id = pc.owner_id
            WHERE pc.is_retired = FALSE
              AND COALESCE(p.action_energy, p.energy, 0) >= 10
              AND COALESCE(p.coins, 0) >= 100
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            print("SKIP: no suitable card/player for drill smoke test")
        else:
            card_id, owner_id = row
            cur.execute(
                "SELECT public.process_stat_drill(%s, %s, %s)",
                (owner_id, card_id, "pac_sprint"),
            )
            print("OK: process_stat_drill succeeded for card", card_id, "->", cur.fetchone()[0])
