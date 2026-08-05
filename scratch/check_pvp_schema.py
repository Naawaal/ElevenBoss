"""Check actual DB column names for player_cards and squad_assignments."""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

ROOT = Path(".").resolve()
load_dotenv(ROOT / ".env")
url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'player_cards'
            AND column_name IN ('def', 'def_stat')
        """)
        pc_cols = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'squad_assignments'
            AND column_name IN ('card_id', 'player_card_id', 'slot', 'position_slot', 'position')
        """)
        sa_cols = [r[0] for r in cur.fetchall()]

        # Check if global_lp is ever updated via PERFORM/UPDATE in finalize RPCs
        cur.execute("""
            SELECT prosrc FROM pg_proc
            WHERE proname = 'finalize_pvp_match'
            AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname='public')
            LIMIT 1
        """)
        src_row = cur.fetchone()
        has_lp_update = "global_lp" in (src_row[0] if src_row else "")

        print("player_cards defense columns:", pc_cols)
        print("squad_assignments key columns:", sa_cols)
        print("finalize_pvp_match writes global_lp:", has_lp_update)
