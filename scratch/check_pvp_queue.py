"""Bump pvp_backfill_daily_limit to 10 in game_config."""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path(".").resolve() / ".env")
url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO public.game_config (key, value_json)
            VALUES ('pvp_backfill_daily_limit', '10')
            ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
        """)
        conn.commit()
        cur.execute("SELECT value_json FROM public.game_config WHERE key = 'pvp_backfill_daily_limit'")
        print("pvp_backfill_daily_limit now:", cur.fetchone()[0])
