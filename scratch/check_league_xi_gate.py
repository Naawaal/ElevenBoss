"""Read-only: which league clubs would fail the XI gate (silent no-match cause)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

with psycopg.connect(dsn, row_factory=dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.season_number, s.status, s.current_matchday
            FROM public.league_seasons s
            WHERE s.status NOT IN ('completed', 'cancelled')
            ORDER BY s.created_at DESC NULLS LAST
            LIMIT 5
            """
        )
        seasons = cur.fetchall()
        print("=== open seasons ===")
        for s in seasons:
            print(f"  {s['id']} #{s['season_number']} status={s['status']} md={s['current_matchday']}")

        if not seasons:
            raise SystemExit(0)

        season_id = seasons[0]["id"]
        cur.execute(
            """
            SELECT
              f.id, f.matchday, f.is_played,
              f.home_team_id, f.away_team_id,
              f.window_start, f.window_end
            FROM public.league_fixtures f
            WHERE f.season_id = %s AND f.is_played = false
            ORDER BY f.matchday, f.id
            LIMIT 20
            """,
            (season_id,),
        )
        fixtures = cur.fetchall()
        print(f"=== unplayed fixtures (season {season_id}) ===")
        for f in fixtures:
            print(
                f"  md{f['matchday']} {f['home_team_id']} vs {f['away_team_id']} "
                f"window={f['window_start']}..{f['window_end']}"
            )

        club_ids = sorted(
            {f["home_team_id"] for f in fixtures} | {f["away_team_id"] for f in fixtures}
        )
        if not club_ids:
            raise SystemExit(0)

        cur.execute(
            """
            SELECT
              p.discord_id,
              p.club_name,
              COALESCE(p.is_ai, false) AS is_ai,
              COALESCE(p.squad_invalid, false) AS squad_invalid,
              (
                SELECT COUNT(*)::int FROM public.squad_assignments sa
                WHERE sa.discord_id = p.discord_id
              ) AS xi_count
            FROM public.players p
            WHERE p.discord_id = ANY(%s)
            ORDER BY p.discord_id
            """,
            (club_ids,),
        )
        print("=== XI gate state ===")
        for r in cur.fetchall():
            flag = ""
            if not r["is_ai"] and (r["squad_invalid"] or r["xi_count"] != 11):
                flag = "  <-- BLOCKS MATCH"
            print(
                f"  {r['discord_id']} {str(r['club_name'])[:22]:22} ai={r['is_ai']} "
                f"squad_invalid={r['squad_invalid']} xi={r['xi_count']}{flag}"
            )
