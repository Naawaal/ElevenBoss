"""Smoke: process_recovery_batch exists and rejects bad batch sizes (no live debit).

Usage:
  python scratch/smoke_dev_hub_recovery.py
"""
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


def main() -> None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regprocedure('public.process_recovery_batch(bigint,uuid[])') IS NOT NULL"
            )
            assert cur.fetchone()[0], "process_recovery_batch missing"

            cur.execute(
                "SELECT to_regprocedure('public.process_recovery_session(bigint,uuid)') IS NOT NULL"
            )
            assert cur.fetchone()[0], "process_recovery_session missing"

            # Empty / oversized arrays must fail without mutating
            for bad in ([], None):
                try:
                    cur.execute(
                        "SELECT public.process_recovery_batch(%s, %s::uuid[])",
                        (0, bad),
                    )
                    raise SystemExit(f"expected reject for batch={bad!r}")
                except psycopg.Error as exc:
                    conn.rollback()
                    msg = str(exc)
                    assert "Select between 1 and 3 players" in msg, msg

            print("smoke_dev_hub_recovery: OK (RPC present; empty batch rejected)")


if __name__ == "__main__":
    main()
