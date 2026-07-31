"""Check ownership history + remaining unclaimed gifts."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
ids = [
    "641e64ec-e09f-4ae0-b3c8-291f49c5a08d",
    "766d5e9e-4e7a-4611-a636-64f16b46f2ee",
]

with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='card_ownership_history' "
        "ORDER BY ordinal_position"
    )
    print("ownership cols", [r["column_name"] for r in cur.fetchall()])
    cur.execute(
        "SELECT * FROM public.card_ownership_history WHERE card_id = ANY(%s::uuid[])",
        (ids,),
    )
    rows = cur.fetchall()
    print("ownership rows", len(rows))
    for r in rows:
        print({k: v for k, v in r.items() if v is not None})

    cur.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE dm_status = 'pending' AND NOT claimed) AS pending_dm,
          COUNT(*) FILTER (WHERE NOT claimed) AS unclaimed,
          COUNT(*) FILTER (WHERE claimed) AS claimed
        FROM public.manager_card_gifts
        """
    )
    print(cur.fetchone())
