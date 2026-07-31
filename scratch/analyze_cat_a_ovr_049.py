"""Analyze unexpected Category A OVR deltas after repair."""
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
            SELECT repair_category,
                   COUNT(*) AS n,
                   COUNT(*) FILTER (WHERE old_overall <> new_overall) AS ovr_changed,
                   COUNT(*) FILTER (WHERE refund_sp > 0) AS with_sp,
                   COALESCE(SUM(ABS(old_overall - new_overall)) FILTER (
                     WHERE old_overall <> new_overall), 0)::int AS abs_ovr_delta_sum
            FROM public.potential_cap_repair_audit
            WHERE batch_id = %s
            GROUP BY 1
            ORDER BY 1
            """,
            (BATCH,),
        )
        print("by_cat", cur.fetchall())

        cur.execute(
            """
            SELECT c.name, a.rarity, a.old_overall, a.new_overall,
                   a.old_potential, a.new_potential,
                   a.old_stats = a.new_stats AS stats_same,
                   a.refund_sp
            FROM public.potential_cap_repair_audit a
            LEFT JOIN public.player_cards c ON c.id = a.card_id
            WHERE a.batch_id = %s
              AND a.repair_category = 'A'
              AND a.old_overall <> a.new_overall
            ORDER BY ABS(a.old_overall - a.new_overall) DESC, c.name
            LIMIT 20
            """,
            (BATCH,),
        )
        print("top_A_ovr_deltas:")
        for r in cur.fetchall():
            print(
                f"  {r['name']} {r['rarity']} "
                f"OVR {r['old_overall']}->{r['new_overall']} "
                f"POT {r['old_potential']}->{r['new_potential']} "
                f"stats_same={r['stats_same']} sp={r['refund_sp']}"
            )

        cur.execute(
            """
            SELECT COUNT(*) AS n,
                   MIN(new_overall - old_overall) AS min_d,
                   MAX(new_overall - old_overall) AS max_d,
                   AVG(new_overall - old_overall)::numeric(6,2) AS avg_d
            FROM public.potential_cap_repair_audit
            WHERE batch_id = %s
              AND repair_category = 'A'
              AND old_overall <> new_overall
            """,
            (BATCH,),
        )
        print("A_ovr_delta_stats", cur.fetchone())
