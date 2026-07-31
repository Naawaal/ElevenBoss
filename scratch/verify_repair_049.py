"""Post-repair verification for batch rarity_pot_fix_20260731."""
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
        cur.execute("SELECT public.count_potential_integrity_anomalies() AS n")
        print("anomalies", cur.fetchone()["n"])

        cur.execute(
            """
            SELECT refund_confidence,
                   COUNT(*) AS cards,
                   COALESCE(SUM(refund_sp), 0)::int AS sp,
                   COALESCE(SUM(refund_coins), 0)::int AS coins,
                   COALESCE(SUM(refund_energy), 0)::int AS energy
            FROM public.potential_cap_repair_audit
            WHERE batch_id = %s
            GROUP BY 1
            ORDER BY 1
            """,
            (BATCH,),
        )
        print("audit_by_confidence", cur.fetchall())

        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM public.potential_cap_repair_audit
            WHERE batch_id = %s
              AND (
                new_overall > new_potential
                OR new_potential > public.rarity_potential_cap(rarity)
                OR COALESCE(new_base_potential, 0) > public.rarity_potential_cap(rarity)
              )
            """,
            (BATCH,),
        )
        print("audit_still_invalid", cur.fetchone()["n"])

        # Coin/energy refunds would hit economy_ledger; this batch is SP-only (0 coins).
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM public.economy_ledger
            WHERE idempotency_key LIKE %s
               OR COALESCE(source, '') ILIKE %s
            """,
            (f"%{BATCH}%", "%potential_cap%"),
        )
        print("economy_ledger_hits_expected_0", cur.fetchone()["n"])
        cur.execute(
            """
            SELECT SUM(refund_sp)::int AS sp_returned,
                   COUNT(*) FILTER (WHERE refund_sp > 0) AS cards_with_sp
            FROM public.potential_cap_repair_audit
            WHERE batch_id = %s
            """,
            (BATCH,),
        )
        print("sp_refunds", cur.fetchone())

        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE notified_at IS NULL) AS pending_dm,
                   COUNT(*) FILTER (WHERE notified_at IS NOT NULL) AS notified
            FROM public.potential_cap_repair_audit
            WHERE batch_id = %s
            """,
            (BATCH,),
        )
        print("notify_status", cur.fetchone())

        cur.execute(
            """
            SELECT conname, convalidated
            FROM pg_constraint
            WHERE conrelid = 'public.player_cards'::regclass
              AND (conname ILIKE '%potential%' OR conname ILIKE '%rarity%')
            ORDER BY 1
            """
        )
        print("player_cards_constraints", cur.fetchall())
