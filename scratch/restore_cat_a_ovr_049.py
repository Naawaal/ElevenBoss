"""Restore Category A stored OVR overwritten by incidental recalculate_card_ovr."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
BATCH = "rarity_pot_fix_20260731"

with psycopg.connect(dsn, row_factory=dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.player_cards pc
            SET overall = a.old_overall
            FROM public.potential_cap_repair_audit a
            WHERE a.batch_id = %s
              AND a.card_id = pc.id
              AND a.repair_category = 'A'
              AND a.old_overall <> a.new_overall
              AND a.old_stats = a.new_stats
              AND a.old_overall <= a.new_potential
            """,
            (BATCH,),
        )
        restored_cards = cur.rowcount
        cur.execute(
            """
            UPDATE public.potential_cap_repair_audit
            SET new_overall = old_overall
            WHERE batch_id = %s
              AND repair_category = 'A'
              AND old_overall <> new_overall
              AND old_stats = new_stats
              AND old_overall <= new_potential
            """,
            (BATCH,),
        )
        restored_audit = cur.rowcount
        cur.execute("SELECT public.count_potential_integrity_anomalies() AS n")
        anomalies = cur.fetchone()["n"]
    conn.commit()
    print(
        f"restored_cards={restored_cards} restored_audit={restored_audit} "
        f"anomalies={anomalies}"
    )
