"""Install count_potential_integrity_anomalies (idempotent)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

CREATE = """
CREATE OR REPLACE FUNCTION public.count_potential_integrity_anomalies()
RETURNS INTEGER
LANGUAGE sql
STABLE
AS $$
    SELECT COUNT(*)::INTEGER
    FROM public.player_cards
    WHERE public.rarity_potential_cap(rarity) IS NULL
       OR potential > public.rarity_potential_cap(rarity)
       OR (
            base_potential IS NOT NULL
            AND base_potential > public.rarity_potential_cap(rarity)
       )
       OR overall > potential;
$$;
"""
GRANT = """
GRANT EXECUTE ON FUNCTION public.count_potential_integrity_anomalies()
    TO anon, authenticated, service_role;
"""

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(CREATE)
        cur.execute(GRANT)
        cur.execute("SELECT public.count_potential_integrity_anomalies()")
        print("anomalies", cur.fetchone()[0])
    conn.commit()
