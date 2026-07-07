#!/usr/bin/env python3
"""Optional soft coin rebalance for hyperinflation (US-25 ops tool).

Applies: coins = floor(coins * factor) + bonus for players with coins > threshold.
Dry-run by default — pass --apply to execute.
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="Soft rebalance player coin balances")
    parser.add_argument("--factor", type=float, default=0.7, help="Multiply balances by this factor")
    parser.add_argument("--bonus", type=int, default=5000, help="Flat bonus after factor")
    parser.add_argument("--threshold", type=int, default=250_000, help="Only rebalance above this balance")
    parser.add_argument("--apply", action="store_true", help="Execute UPDATE (default dry-run)")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found", file=sys.stderr)
        return 1

    dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
    sql_select = """
        SELECT discord_id, coins,
               GREATEST(0, (coins * %s)::BIGINT) + %s AS new_coins
        FROM players
        WHERE coins > %s AND NOT is_ai
    """
    sql_update = """
        UPDATE players
        SET coins = GREATEST(0, (coins * %s)::BIGINT) + %s
        WHERE coins > %s AND NOT is_ai
    """

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_select, (args.factor, args.bonus, args.threshold))
            rows = cur.fetchall()
            print(f"Would rebalance {len(rows)} clubs (threshold>{args.threshold:,})")
            for discord_id, old, new in rows[:10]:
                print(f"  {discord_id}: {old:,} -> {new:,}")
            if len(rows) > 10:
                print(f"  ... and {len(rows) - 10} more")

            if args.apply and rows:
                cur.execute(sql_update, (args.factor, args.bonus, args.threshold))
                conn.commit()
                print(f"Applied rebalance to {cur.rowcount} rows.")
            elif not args.apply:
                print("Dry run — pass --apply to execute")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
