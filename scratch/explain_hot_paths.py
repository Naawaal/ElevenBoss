"""EXPLAIN candidates for US-43 indexes (T003/T015).

Requires DATABASE_URL. Writes text under scratch/explain_snapshots/.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scratch" / "explain_snapshots"
load_dotenv(ROOT / ".env")

QUERIES = {
    "league_fixtures_season_matchday": """
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM public.league_fixtures
WHERE season_id = (SELECT id FROM public.league_seasons LIMIT 1)
  AND matchday = 1
LIMIT 50;
""",
    "league_fixtures_unplayed": """
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM public.league_fixtures
WHERE season_id = (SELECT id FROM public.league_seasons LIMIT 1)
  AND is_played = false
LIMIT 50;
""",
    "economy_ledger_club": """
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM public.economy_ledger
WHERE club_id = (SELECT discord_id FROM public.players LIMIT 1)
ORDER BY created_at DESC
LIMIT 50;
""",
}


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set — skipping live EXPLAIN")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for name, sql in QUERIES.items():
                try:
                    cur.execute(sql)
                    rows = cur.fetchall()
                    text = "\n".join(r[0] for r in rows)
                except Exception as exc:
                    text = f"ERROR: {exc}"
                    conn.rollback()
                path = OUT / f"{stamp}_{name}.txt"
                path.write_text(text, encoding="utf-8")
                print(f"Wrote {path.name} ({len(text)} bytes)")


if __name__ == "__main__":
    main()
