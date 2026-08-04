"""Lightweight soak report for Feature 053 Ranked PvP (read-only)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT key, value_json #>> '{}'
            FROM public.game_config
            WHERE key LIKE 'battle_pvp%' OR key LIKE 'pvp_%'
            ORDER BY key
            """
        )
        print("=== game_config (pvp*) ===")
        for k, v in cur.fetchall():
            print(f"  {k} = {v}")

        cur.execute(
            """
            SELECT status, COUNT(*)
            FROM public.pvp_matchmaking_queue
            GROUP BY status
            ORDER BY status
            """
        )
        print("\n=== queue by status ===")
        rows = cur.fetchall()
        if not rows:
            print("  (empty)")
        for s, n in rows:
            print(f"  {s}: {n}")

        cur.execute(
            """
            SELECT status, COUNT(*)
            FROM public.match_runs
            WHERE run_type = 'pvp'
            GROUP BY status
            ORDER BY status
            """
        )
        print("\n=== match_runs pvp by status ===")
        rows = cur.fetchall()
        if not rows:
            print("  (empty)")
        for s, n in rows:
            print(f"  {s}: {n}")

        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE status = 'active'),
                   COUNT(*) FILTER (WHERE status = 'tracking'),
                   COUNT(*) FILTER (WHERE status = 'dormant'),
                   COUNT(*)
            FROM public.manager_rivalries
            """
        )
        a, t, d, total = cur.fetchone()
        print(f"\n=== rivalries active={a} tracking={t} dormant={d} total={total} ===")

        cur.execute("SELECT COUNT(*) FROM public.pvp_blocks")
        print(f"=== pvp_blocks: {cur.fetchone()[0]} ===")

        cur.execute(
            """
            SELECT COUNT(*) FROM public.match_history
            WHERE match_type = 'pvp' AND played_at > NOW() - INTERVAL '7 days'
            """
        )
        print(f"=== ranked history last 7d: {cur.fetchone()[0]} ===")

print("\nSoak report done. Enable flags only after 052 ACCEPT + internal soak.")
