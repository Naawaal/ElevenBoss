"""Smoke / sample for League Dynamics (020).

Prints assign_dynamics_windows sample and reads the feature flag when DATABASE_URL is set.
Optional MoMD RPC is skipped unless SMOKE_MOMD=1 and season/matchday env vars are set.

Usage:
  python scratch/smoke_league_dynamics.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "leagues"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from leagues import assign_dynamics_windows  # noqa: E402


def main() -> None:
    now = datetime(2026, 7, 15, 14, 30, tzinfo=timezone.utc)
    windows = assign_dynamics_windows(now, 14)
    print(f"assign_dynamics_windows({now.isoformat()}, 14) -> {len(windows)} matchdays")
    for w in windows[:3]:
        print(
            f"  MD{w['matchday']}: "
            f"{w['window_start'].isoformat()} -> {w['window_end'].isoformat()}"
        )
    print(f"  ... MD{windows[-1]['matchday']}: ends {windows[-1]['window_end'].isoformat()}")

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set — skipping flag / RPC checks.")
        return

    import psycopg

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT public.league_dynamics_enabled()")
                enabled = cur.fetchone()[0]
                print(f"league_dynamics_enabled() = {enabled!r}")
            except Exception as exc:
                print(f"Flag RPC unavailable (apply migration 064?): {exc}")
                conn.rollback()
                return

            cur.execute(
                """
                SELECT pacing_mode, COUNT(*)
                FROM public.league_seasons
                WHERE status = 'active'
                GROUP BY pacing_mode
                """
            )
            rows = cur.fetchall()
            if rows:
                print("Active seasons by pacing_mode:")
                for mode, cnt in rows:
                    print(f"  {mode or 'NULL(legacy)'}: {cnt}")
            else:
                print("No active seasons.")

            if os.environ.get("SMOKE_MOMD") == "1":
                season_id = os.environ.get("SMOKE_SEASON_ID")
                md = int(os.environ.get("SMOKE_MATCHDAY", "1"))
                if not season_id:
                    print("SMOKE_MOMD=1 but SMOKE_SEASON_ID unset — skip MoMD RPC.")
                    return
                cur.execute(
                    "SELECT public.award_manager_of_the_matchday(%s::uuid, %s)",
                    (season_id, md),
                )
                result = cur.fetchone()[0]
                if isinstance(result, str):
                    result = json.loads(result)
                print("MoMD RPC:", json.dumps(result, default=str))
                conn.commit()


if __name__ == "__main__":
    main()
