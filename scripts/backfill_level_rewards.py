"""Idempotent backfill for pending_level_rewards (ops / post-migration)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

_LEVEL_SYNC = """
UPDATE public.player_cards
SET level = public.level_from_xp(COALESCE(xp, 0))
WHERE level IS DISTINCT FROM public.level_from_xp(COALESCE(xp, 0));
"""

_BACKFILL = """
INSERT INTO public.pending_level_rewards (club_id, player_id, missing_points)
SELECT
    c.owner_id,
    c.id,
    LEAST(
        18,
        GREATEST(
            1,
            (((public.level_from_xp(COALESCE(c.xp, 0)) - 1) * 3
              - COALESCE(c.skill_points_earned, 0)) * 75) / 100
        )
    )
FROM public.player_cards c
WHERE (public.level_from_xp(COALESCE(c.xp, 0)) - 1) * 3 > COALESCE(c.skill_points_earned, 0)
ON CONFLICT (player_id) DO UPDATE
SET
    club_id = EXCLUDED.club_id,
    missing_points = EXCLUDED.missing_points
WHERE NOT pending_level_rewards.claimed;
"""


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1

    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(_LEVEL_SYNC)
            cur.execute(_BACKFILL)
            cur.execute(
                "SELECT COUNT(*) FROM public.pending_level_rewards WHERE NOT claimed"
            )
            pending = cur.fetchone()[0]

    print(f"Backfill complete. Unclaimed pending rows: {pending}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
