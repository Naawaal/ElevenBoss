import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg

ROOT = Path(".").resolve()
load_dotenv(ROOT / ".env")
url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT public.build_calibrated_pvp_ai_snapshot(85.0, 'Elite')")
        res = cur.fetchone()[0]
        import json
        print(json.dumps(res, indent=2))
