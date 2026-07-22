"""Smoke-check assert_club_action_allowed / register RPCs after 076."""
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
            SELECT to_regprocedure('public.assert_club_action_allowed(bigint,text)') IS NOT NULL,
                   to_regprocedure('public.register_league_season(bigint,bigint,uuid,jsonb)') IS NOT NULL,
                   to_regprocedure('public.register_league_membership(bigint,bigint)') IS NOT NULL
            """
        )
        print("procs:", cur.fetchone())

        cur.execute(
            """
            SELECT discord_id FROM public.players
            WHERE COALESCE(is_ai, FALSE) = FALSE
            ORDER BY last_qualifying_activity_at ASC NULLS FIRST
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            print("no human club — existence OK")
            raise SystemExit(0)
        club_id = row[0]

        # Force abandoned for assert test then rollback
        cur.execute(
            """
            UPDATE public.players
            SET last_qualifying_activity_at = NOW() - INTERVAL '100 days',
                identity_status = 'abandoned'
            WHERE discord_id = %s
            """,
            (club_id,),
        )
        try:
            cur.execute(
                "SELECT public.assert_club_action_allowed(%s, 'league_join')",
                (club_id,),
            )
            print("UNEXPECTED: abandoned league_join allowed")
        except psycopg.Error as e:
            print("OK abandoned join blocked:", str(e).split("\n")[0])
        conn.rollback()
        print("smoke 076 OK")
