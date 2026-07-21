"""Verify migration 069 objects exist."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")

dsn = url.replace("postgresql+asyncpg://", "postgresql://")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='players'
              AND column_name='last_consumed_topgg_vote_at'
            """
        )
        print("column last_consumed_topgg_vote_at:", bool(cur.fetchone()))

        cur.execute(
            "SELECT to_regprocedure('public.claim_daily_pack(bigint,jsonb,timestamptz)') IS NOT NULL"
        )
        print("rpc 3-arg:", cur.fetchone()[0])

        cur.execute(
            "SELECT to_regprocedure('public.claim_daily_pack(bigint,jsonb)') IS NOT NULL"
        )
        print("rpc 2-arg (should be false):", cur.fetchone()[0])

        cur.execute(
            """
            SELECT key, value_json::text FROM game_config
            WHERE key IN ('daily_pack_cooldown_hours','topgg_vote_bypass_enabled')
            ORDER BY key
            """
        )
        print("game_config:", cur.fetchall())
