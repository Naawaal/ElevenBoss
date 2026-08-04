import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT proname, pg_get_function_identity_arguments(p.oid)
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND proname = 'process_match_result'
        """)
        print("process_match_result overloads:", cur.fetchall())
