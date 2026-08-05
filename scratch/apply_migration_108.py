"""Apply migration 108_match_concurrency_integrity.sql to database."""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path('.').resolve() / '.env')
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')

sql_path = Path('.').resolve() / 'supabase' / 'migrations' / '108_match_concurrency_integrity.sql'
sql_text = sql_path.read_text(encoding='utf-8')

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_text)
    conn.commit()

print("Successfully applied migration 108_match_concurrency_integrity.sql!")
