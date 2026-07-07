import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
dsn = os.getenv("DATABASE_URL").replace("postgresql+asyncpg://", "postgresql://")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='player_cards' AND column_name LIKE 'skill%'"
        )
        print("columns:", [r[0] for r in cur.fetchall()])
        cur.execute(
            "SELECT proname, pg_get_function_identity_arguments(p.oid) FROM pg_proc p "
            "WHERE proname IN ('apply_card_xp','level_from_xp','claim_pending_level_rewards')"
        )
        print("funcs:", cur.fetchall())
        cur.execute("SELECT to_regclass('public.pending_level_rewards')")
        print("pending table:", cur.fetchone())
