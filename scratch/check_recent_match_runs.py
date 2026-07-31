"""Read-only: recent match_runs + league fixture play state."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='match_runs' ORDER BY ordinal_position"
    )
    cols = [r["column_name"] for r in cur.fetchall()]
    print("match_runs columns:", cols)

    cur.execute("SELECT * FROM public.match_runs ORDER BY started_at DESC LIMIT 12")
    print("=== recent match_runs ===")
    for r in cur.fetchall():
        r.pop("squad_snapshot", None)
        print("  ", {k: v for k, v in r.items() if v is not None})

    cur.execute(
        """
        SELECT id, matchday, home_team_id, away_team_id, is_played, engine_version,
               home_score, away_score, played_at
        FROM public.league_fixtures
        WHERE season_id = (
            SELECT id FROM public.league_seasons WHERE status = 'active'
            ORDER BY created_at DESC LIMIT 1
        )
        ORDER BY played_at DESC NULLS LAST, matchday
        LIMIT 12
        """
    )
    print("=== most recently played fixtures ===")
    for r in cur.fetchall():
        print("  ", r)

    cur.execute("SELECT * FROM public.match_locks ORDER BY created_at DESC LIMIT 10")
    print("=== match_locks ===")
    for r in cur.fetchall():
        print("  ", r)
