"""Smoke-check migration 074 identity ownership objects."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set in .env")

dsn = url.replace("postgresql+asyncpg://", "postgresql://")

required_cols = (
    "identity_status",
    "last_qualifying_activity_at",
    "identity_status_changed_at",
)
required_fns = (
    "touch_club_activity(bigint)",
    "classify_club_identity_status(bigint)",
    "recover_club_identity(bigint)",
    "register_new_player(bigint,text,text,text,jsonb)",
)

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        for col in required_cols:
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'players'
                  AND column_name = %s
                """,
                (col,),
            )
            if cur.fetchone() is None:
                raise SystemExit(f"Missing column players.{col}")

        for sig in required_fns:
            cur.execute("SELECT to_regprocedure(%s)", (f"public.{sig}",))
            if cur.fetchone()[0] is None:
                raise SystemExit(f"Missing function public.{sig}")

        # Idempotency: second register on existing id must raise ALREADY_REGISTERED
        cur.execute("SELECT discord_id FROM public.players WHERE is_ai = FALSE LIMIT 1")
        row = cur.fetchone()
        if row:
            club_id = row[0]
            try:
                cur.execute(
                    "SELECT public.register_new_player(%s, %s, %s, %s, %s::jsonb)",
                    (club_id, "smoke", "Smoke FC", "Smoke Manager", "[]"),
                )
                conn.rollback()
                raise SystemExit("Expected ALREADY_REGISTERED on second register")
            except psycopg.Error as e:
                conn.rollback()
                if "ALREADY_REGISTERED" not in str(e):
                    raise SystemExit(f"Unexpected register error: {e}") from e

            # Classify must not delete the club
            cur.execute("SELECT public.classify_club_identity_status(%s)", (club_id,))
            cur.execute("SELECT 1 FROM public.players WHERE discord_id = %s", (club_id,))
            if cur.fetchone() is None:
                raise SystemExit("classify deleted club — forbidden")

print("Smoke 074 OK — identity columns/RPCs present; register idempotent; classify non-delete.")
