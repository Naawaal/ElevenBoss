import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT key, value_json FROM game_config WHERE key LIKE 'age_xp_mult_%' ORDER BY key")
        print("game_config:", cur.fetchall())
        try:
            cur.execute("SELECT public.card_xp_age_multiplier(19)")
            print("multiplier:", cur.fetchone()[0])
        except Exception as e:
            print("card_xp_age_multiplier error:", e)
