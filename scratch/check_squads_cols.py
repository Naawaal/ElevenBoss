import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'squads'")
        print("squads cols:", [r[0] for r in cur.fetchall()])
