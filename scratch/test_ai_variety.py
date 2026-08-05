import os, json
from pathlib import Path
from dotenv import load_dotenv
import psycopg

ROOT = Path(".").resolve()
load_dotenv(ROOT / ".env")
url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        results = []
        for _ in range(3):
            cur.execute("SELECT public.build_calibrated_pvp_ai_snapshot(%s, %s)", (75, "Elite"))
            results.append(cur.fetchone()[0])

clubs      = [r["club_name"] for r in results]
formations = [r["formation"] for r in results]
tactics    = [r["tactics"]["stance"] for r in results]
print("Club names :", clubs)
print("Formations :", formations)
print("Tactics    :", tactics)
print("All same?  :", len(set(clubs)) == 1 and len(set(formations)) == 1)
