"""Inspect details for league_channel_id 1011315126995009566."""
import os, asyncio
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path('.').resolve() / '.env')
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT guild_id, league_channel_id, announcement_role_id
            FROM public.guild_config
            WHERE league_channel_id IS NOT NULL
        """)
        for r in cur.fetchall():
            print(f"Guild ID: {r[0]} -> Configured Channel ID: {r[1]}")
