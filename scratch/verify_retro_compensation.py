"""One-off verification for retro compensation fix (rollback-safe)."""
from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1

    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.discord_id FROM players p
                WHERE NOT EXISTS (
                  SELECT 1 FROM pending_level_rewards pr
                  JOIN player_cards c ON c.id = pr.player_id
                  WHERE c.owner_id = p.discord_id AND NOT pr.claimed
                )
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                cur.execute("SELECT count_unclaimed_level_rewards(%s)", (row[0],))
                count = cur.fetchone()[0]
                assert count == 0, f"expected 0 unclaimed for clean owner, got {count}"
                print(f"no-pending owner {row[0]}: count_unclaimed=0 OK")

            cur.execute(
                "SELECT proname FROM pg_proc WHERE proname = 'assert_not_in_match'"
            )
            assert cur.fetchone(), "assert_not_in_match missing"
            print("assert_not_in_match RPC: OK")

    print("verify_retro_compensation: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
