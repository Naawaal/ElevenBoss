"""Apply migration 109_fix_start_friendly_match_id_type.sql to database."""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

load_dotenv(Path('.').resolve() / '.env')
url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')

sql_path = Path('.').resolve() / 'supabase' / 'migrations' / '109_fix_start_friendly_match_id_type.sql'
sql_text = sql_path.read_text(encoding='utf-8')

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(sql_text)
    conn.commit()

print("Successfully applied migration 109_fix_start_friendly_match_id_type.sql!")
