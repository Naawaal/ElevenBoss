"""Smoke-check process_stat_drill boost JSON shape after 078 (no live drill charge)."""
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
            "SELECT to_regprocedure('public.process_stat_drill(bigint,uuid,text)') IS NOT NULL"
        )
        assert cur.fetchone()[0], "process_stat_drill missing"
        cur.execute(
            """
            SELECT pg_get_functiondef(
                'public.process_stat_drill(bigint,uuid,text)'::regprocedure
            )
            """
        )
        body = cur.fetchone()[0]
        assert "peek_card_ovr" in body
        assert "stat_boosted" in body
        assert "boost_block_reason" in body
        assert "assert_card_action_allowed" in body
        assert "stat_at_maximum" in body
        assert "would_exceed_potential" in body
    conn.commit()
print("smoke_drill_stat_boost_078 OK — boost soft-fail keys present in process_stat_drill")
