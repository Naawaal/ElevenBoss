"""Apply migration 057 and run backfill_injury_eta_fairness once.

Usage:
  python scratch/apply_migration_057.py
  python scratch/apply_migration_057.py --notify
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--notify",
        action="store_true",
        help="After backfill, best-effort DM managers for early discharges",
    )
    parser.add_argument(
        "--skip-apply",
        action="store_true",
        help="Only invoke RPC (migration already applied)",
    )
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set in .env")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    sql_path = ROOT / "supabase" / "migrations" / "057_hospital_eta_backfill.sql"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            if not args.skip_apply:
                print(f"Applying {sql_path.name} ...")
                cur.execute(sql_path.read_text(encoding="utf-8"))
            print("Running backfill_injury_eta_fairness() ...")
            cur.execute("SELECT public.backfill_injury_eta_fairness()")
            row = cur.fetchone()
            summary = row[0] if row else {}
        conn.commit()

    print(json.dumps(summary, indent=2, default=str))

    early = summary.get("early_discharged") if isinstance(summary, dict) else None
    if args.notify and early:
        notify = ROOT / "scratch" / "notify_hospital_eta_backfill.py"
        payload_path = ROOT / "scratch" / "_eta_backfill_early.json"
        payload_path.write_text(json.dumps(early), encoding="utf-8")
        try:
            subprocess.run(
                [sys.executable, str(notify), "--from-file", str(payload_path)],
                check=False,
            )
        finally:
            if payload_path.exists():
                payload_path.unlink()
    elif args.notify:
        print("No early discharges to notify.")


if __name__ == "__main__":
    main()
