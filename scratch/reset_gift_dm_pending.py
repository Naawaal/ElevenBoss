"""Reset blocked unclaimed gifts so deploy notifier can retry DMs."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute(
        """
        UPDATE public.manager_card_gifts
        SET dm_status = 'pending'
        WHERE claimed = FALSE AND dm_status = 'blocked'
        """
    )
    print("reset blocked->pending", cur.rowcount)
    conn.commit()
    cur.execute(
        """
        SELECT dm_status, claimed, COUNT(*)
        FROM public.manager_card_gifts
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    )
    print(cur.fetchall())
