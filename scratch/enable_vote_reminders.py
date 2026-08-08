"""Check/enable topgg_vote_reminders_enabled in game_config."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

env_flag = os.environ.get("TOPGG_VOTE_REMINDERS_ENABLED", "<unset defaults true>")
print("TOPGG_VOTE_REMINDERS_ENABLED=", env_flag)
print("TOPGG_TOKEN_set=", bool(os.environ.get("TOPGG_TOKEN", "").strip()))

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")
dsn = url.replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key, value_json FROM public.game_config "
            "WHERE key = %s",
            ("topgg_vote_reminders_enabled",),
        )
        row = cur.fetchone()
        print("before=", row)

        cur.execute(
            """
            INSERT INTO public.game_config (key, value_json)
            VALUES ('topgg_vote_reminders_enabled', 'true'::jsonb)
            ON CONFLICT (key) DO UPDATE
            SET value_json = 'true'::jsonb
            """
        )
        cur.execute(
            "SELECT key, value_json FROM public.game_config "
            "WHERE key = %s",
            ("topgg_vote_reminders_enabled",),
        )
        print("after=", cur.fetchone())
        cur.execute("SELECT count(*) FROM public.topgg_vote_reminders")
        print("reminder_rows=", cur.fetchone()[0])
    conn.commit()
print("enabled")
