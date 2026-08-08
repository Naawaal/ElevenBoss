"""Enable competitive_match_enabled in game_config."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

env = os.environ.get("COMPETITIVE_MATCH_ENABLED")
print("COMPETITIVE_MATCH_ENABLED=", repr(env) if env is not None else "<unset>")

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")
dsn = url.replace("postgresql+asyncpg://", "postgresql://")

keys = (
    "competitive_match_enabled",
    "bot_dynamic_difficulty_enabled",
    "competitive_extra_time_fatigue_multiplier",
    "competitive_extra_time_injury_multiplier",
)

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT key, value_json FROM public.game_config WHERE key = ANY(%s) ORDER BY key",
            (list(keys),),
        )
        print("before:")
        for row in cur.fetchall():
            print(" ", row)

        cur.execute(
            """
            INSERT INTO public.game_config (key, value_json)
            VALUES ('competitive_match_enabled', 'true'::jsonb)
            ON CONFLICT (key) DO UPDATE
            SET value_json = 'true'::jsonb
            """
        )
        cur.execute(
            "SELECT key, value_json FROM public.game_config WHERE key = %s",
            ("competitive_match_enabled",),
        )
        print("after=", cur.fetchone())
    conn.commit()

print("enabled")
if env is not None and str(env).strip().lower() in {"0", "false", "no", "off"}:
    print(
        "WARNING: COMPETITIVE_MATCH_ENABLED env is set to",
        repr(env),
        "— that overrides game_config and keeps competitive OFF until you unset/change it.",
    )
