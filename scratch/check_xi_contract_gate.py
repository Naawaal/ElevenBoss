"""Read-only: which league clubs are blocked by past-grace XI contracts."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

CLUBS = [
    560340920524865539,
    806810293388181514,
    816259135523520512,
    830343973976408074,
    840864839240253440,
    917714032822198333,
    976054227459776582,
]

with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='game_config' ORDER BY ordinal_position"
    )
    print("game_config cols:", [r["column_name"] for r in cur.fetchall()])
    cur.execute("SELECT * FROM public.game_config WHERE key = 'contract_grace_days'")
    row = cur.fetchone()
    print("contract_grace_days row:", row)
    grace = int((row or {}).get("int_value") or (row or {}).get("num_value") or 7)
    print("contract_grace_days =", grace)

    cur.execute(
        """
        SELECT sa.discord_id,
               pc.name,
               pc.contract_expires_at,
               now() - pc.contract_expires_at AS overdue
        FROM public.squad_assignments sa
        JOIN public.player_cards pc ON pc.id = sa.player_card_id
        WHERE sa.discord_id = ANY(%s)
          AND pc.contract_expires_at IS NOT NULL
          AND pc.contract_expires_at + make_interval(days => %s) < now()
        ORDER BY sa.discord_id, pc.contract_expires_at
        """,
        (CLUBS, grace),
    )
    rows = cur.fetchall()
    print("=== past-grace XI contracts (block matches) ===")
    if not rows:
        print("  none")
    for r in rows:
        print(f"  {r['discord_id']} {r['name']} expired {r['contract_expires_at']} (overdue {r['overdue']})")

    cur.execute(
        """
        SELECT sa.discord_id, COUNT(*) FILTER (WHERE pc.contract_expires_at < now()) AS expired_in_grace
        FROM public.squad_assignments sa
        JOIN public.player_cards pc ON pc.id = sa.player_card_id
        WHERE sa.discord_id = ANY(%s)
        GROUP BY sa.discord_id
        ORDER BY sa.discord_id
        """,
        (CLUBS,),
    )
    print("=== expired-but-in-grace counts ===")
    for r in cur.fetchall():
        print("  ", r)
