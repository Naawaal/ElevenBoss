import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT public.build_pvp_squad_snapshot(999103001)")
            print("Snapshot:", cur.fetchone()[0])
        except Exception as e:
            print("Snapshot ERROR:", e)
