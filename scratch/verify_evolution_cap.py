"""Quick post-040 check: no club should have >3 active evolutions."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1
    import psycopg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT owner_id, COUNT(*)::INTEGER
                FROM public.active_evolutions
                WHERE status = 'active' AND owner_id IS NOT NULL
                GROUP BY owner_id
                HAVING COUNT(*) > 3
                ORDER BY COUNT(*) DESC
                """
            )
            overflow = cur.fetchall()
            cur.execute(
                """
                SELECT COUNT(*)::INTEGER
                FROM public.active_evolutions
                WHERE status = 'cancelled'
                  AND cancelled_at > NOW() - INTERVAL '10 minutes'
                """
            )
            recent_cancelled = cur.fetchone()[0]
            cur.execute(
                """
                SELECT owner_id, COUNT(*)::INTEGER
                FROM public.active_evolutions
                WHERE status = 'active' AND owner_id IS NOT NULL
                GROUP BY owner_id
                ORDER BY COUNT(*) DESC
                LIMIT 5
                """
            )
            top = cur.fetchall()
    print("clubs_over_3_slots:", overflow or "none")
    print("cancelled_last_10min:", recent_cancelled)
    print("top_active_counts:", top)
    return 1 if overflow else 0


if __name__ == "__main__":
    raise SystemExit(main())
