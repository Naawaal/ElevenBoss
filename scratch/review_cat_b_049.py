"""Inspect economy_ledger.reason_meta for Category B cards."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
IDS = [
    "4d3eac93-6321-4a97-8849-018ba40b6f86",
    "e68e8456-3847-47e2-9c73-ff66c2ea8b3e",
    "ecbec9b2-3b98-436f-aebe-89cbd04857ed",
    "e0ffc1cf-30db-4d4e-972d-48a2e184bd94",
    "afabb7c4-dde4-49c8-a328-5fc764f9f736",
    "fec7aa4f-f17d-460d-a75d-4578932e96f3",
    "c6b9b1fe-a2b0-44e7-bcb2-e148f352e493",
    "fa287bd6-7c21-4fc0-9f50-7ebdb898f8cf",
]

with psycopg.connect(dsn, row_factory=dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT reason_meta->>'card_id' AS card_id,
                   COUNT(*) AS n,
                   SUM(amount) FILTER (WHERE currency = 'coins') AS coins,
                   SUM(amount) FILTER (WHERE currency IN ('energy', 'action_energy')) AS energy,
                   array_agg(DISTINCT source) AS sources
            FROM public.economy_ledger
            WHERE reason_meta->>'card_id' = ANY(%s)
            GROUP BY 1
            ORDER BY 1
            """,
            (IDS,),
        )
        rows = cur.fetchall()
        print("hits", len(rows))
        for r in rows:
            print(r)
        if not rows:
            cur.execute(
                """
                SELECT source, currency, amount, reason_meta
                FROM public.economy_ledger
                WHERE reason_meta::text ILIKE '%4d3eac93%'
                LIMIT 5
                """
            )
            print("sample ilike", cur.fetchall())
