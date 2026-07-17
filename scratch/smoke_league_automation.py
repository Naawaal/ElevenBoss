"""Smoke / sample for League Automation (021).

Prints next_monday_0005_utc, global flag, and automation registration seasons.

Usage:
  python scratch/smoke_league_automation.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "leagues"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from leagues import next_monday_0005_utc  # noqa: E402


def main() -> None:
    now = datetime.now(timezone.utc)
    nxt = next_monday_0005_utc(now)
    print(f"now                    = {now.isoformat()}")
    print(f"next_monday_0005_utc   = {nxt.isoformat()}")

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set — skipping flag / season list.")
        return

    import psycopg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT public.league_automation_enabled()")
                enabled = cur.fetchone()[0]
                print(f"league_automation_enabled() = {enabled!r}")
            except Exception as exc:
                print(f"Flag RPC unavailable (apply migration 065?): {exc}")
                conn.rollback()
                return

            cur.execute(
                """
                SELECT ls.season_number, ls.status, ls.config_json, l.guild_id
                FROM public.league_seasons ls
                JOIN public.leagues l ON l.id = ls.league_id
                WHERE ls.status = 'registration'
                  AND COALESCE((ls.config_json->>'automation')::boolean, false) = true
                ORDER BY ls.season_number DESC
                LIMIT 20
                """
            )
            rows = cur.fetchall()
            if rows:
                print(f"Automation registration seasons ({len(rows)}):")
                for season_number, status, config_json, guild_id in rows:
                    closes = None
                    if isinstance(config_json, dict):
                        closes = config_json.get("registration_closes_at")
                    print(
                        f"  guild={guild_id} season=#{season_number} "
                        f"status={status} closes={closes}"
                    )
            else:
                print("No automation-owned registration seasons.")


if __name__ == "__main__":
    main()
