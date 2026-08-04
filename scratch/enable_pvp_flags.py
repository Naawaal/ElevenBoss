import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.game_config
            SET value_json = '"true"'::jsonb
            WHERE key IN ('battle_pvp_enabled', 'pvp_rewards_enabled', 'pvp_rivalries_enabled')
            """
        )
        conn.commit()
        
        cur.execute(
            """
            SELECT key, value_json #>> '{}'
            FROM public.game_config
            WHERE key IN ('battle_pvp_enabled', 'pvp_rewards_enabled', 'pvp_rivalries_enabled')
            ORDER BY key
            """
        )
        print("Updated PvP flags in game_config:")
        for key, val in cur.fetchall():
            print(f"  {key}: {val}")
