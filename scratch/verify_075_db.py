"""Re-verify migration 075 objects + schema guard on DATABASE_URL."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

sql = (ROOT / "supabase" / "migrations" / "075_player_card_state_guards.sql").read_text(
    encoding="utf-8"
)
verify = (ROOT / "supabase" / "scripts" / "verify_required_schema.sql").read_text(
    encoding="utf-8"
)

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        # Idempotent re-apply (CREATE OR REPLACE)
        print("Re-applying 075 ...")
        cur.execute(sql)
        conn.commit()

        cur.execute(
            """
            SELECT to_regprocedure('public.assert_card_action_allowed(bigint,uuid,text)')::text,
                   to_regprocedure('public.card_primary_state(uuid)')::text
            """
        )
        print("procs:", cur.fetchone())

        cur.execute(
            """
            SELECT COUNT(*) FROM public.player_cards
            WHERE COALESCE(in_hospital, FALSE) = TRUE
            """
        )
        print("hospital cards:", cur.fetchone()[0])

        # Prove matrix block on hospitalized card if any
        cur.execute(
            """
            SELECT owner_id, id FROM public.player_cards
            WHERE COALESCE(in_hospital, FALSE) = TRUE
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row:
            try:
                cur.execute(
                    "SELECT public.assert_card_action_allowed(%s, %s, 'drill')",
                    row,
                )
                print("FAIL: hospital drill allowed")
            except psycopg.Error as e:
                conn.rollback()
                print("OK hospital drill blocked:", str(e).split("\n")[0])

        print("Running verify_required_schema.sql ...")
        cur.execute(verify)
        conn.commit()
        print("verify_required_schema: PASS")
