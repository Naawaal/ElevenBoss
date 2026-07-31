"""EXPLAIN (ANALYZE, BUFFERS) for 050 hot-path query shapes (T029/T036/T064).

Requires DATABASE_URL. Writes under scratch/explain_snapshots/050_*.
Also dumps existing indexes on players / transfer_listings / player_cards.
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

INDEX_DUMP = """
SELECT
  c.relname AS table_name,
  i.relname AS index_name,
  pg_get_indexdef(i.oid) AS index_def
FROM pg_class c
JOIN pg_index x ON x.indrelid = c.oid
JOIN pg_class i ON i.oid = x.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
    'players', 'player_cards', 'transfer_listings',
    'pending_level_rewards', 'support_legendary_rewards',
    'league_participants', 'league_fixtures', 'squad_assignments',
    'active_evolutions', 'active_training'
  )
ORDER BY c.relname, i.relname;
"""

# Inner shapes matching 090/093 RPCs (not wrapped in plpgsql so plans are visible).
QUERIES = {
    "div_lb_count_filter": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT COUNT(*)::int
FROM public.players
WHERE division = (SELECT division FROM public.players WHERE COALESCE(is_ai,false)=false LIMIT 1)
  AND COALESCE(is_ai, false) = false;
""",
    "div_lb_rank_window": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT discord_id, club_name, league_points, goal_difference,
       ROW_NUMBER() OVER (
         ORDER BY league_points DESC, goal_difference DESC, discord_id ASC
       ) AS rank_pos
FROM public.players p
WHERE p.division = (SELECT division FROM public.players WHERE COALESCE(is_ai,false)=false LIMIT 1)
  AND COALESCE(p.is_ai, false) = false;
""",
    "div_lb_viewer_rank": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH v AS (
  SELECT discord_id, division, league_points, goal_difference
  FROM public.players
  WHERE COALESCE(is_ai,false)=false
  LIMIT 1
)
SELECT 1 + COUNT(*)::int
FROM public.players p, v
WHERE p.division = v.division
  AND COALESCE(p.is_ai, false) = false
  AND (
      p.league_points > COALESCE(v.league_points, -1)
      OR (p.league_points = COALESCE(v.league_points, -1)
          AND p.goal_difference > COALESCE(v.goal_difference, -999999))
      OR (p.league_points = COALESCE(v.league_points, -1)
          AND p.goal_difference = COALESCE(v.goal_difference, -999999)
          AND p.discord_id < v.discord_id)
  );
""",
    "global_lb_window": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT discord_id, club_name, global_lp,
       ROW_NUMBER() OVER (ORDER BY global_lp DESC, discord_id ASC) AS rank_pos
FROM public.players p
WHERE COALESCE(p.is_ai, false) = false;
""",
    "browse_active_newest": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT tl.id, tl.price_coins, tl.created_at, tl.expires_at, pc.overall, pc.position
FROM public.transfer_listings tl
JOIN public.player_cards pc ON pc.id = tl.card_id
WHERE tl.status = 'active'
  AND tl.expires_at > NOW()
ORDER BY tl.created_at DESC, tl.id DESC
LIMIT 25;
""",
    "browse_active_price": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT tl.id, tl.price_coins, tl.created_at, pc.overall
FROM public.transfer_listings tl
JOIN public.player_cards pc ON pc.id = tl.card_id
WHERE tl.status = 'active'
  AND tl.expires_at > NOW()
ORDER BY tl.price_coins ASC, tl.created_at DESC, tl.id DESC
LIMIT 25;
""",
    "browse_active_ovr": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT tl.id, tl.price_coins, pc.overall
FROM public.transfer_listings tl
JOIN public.player_cards pc ON pc.id = tl.card_id
WHERE tl.status = 'active'
  AND tl.expires_at > NOW()
ORDER BY pc.overall DESC, tl.created_at DESC, tl.id DESC
LIMIT 25;
""",
    "sell_eligible": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT pc.id, pc.overall
FROM public.player_cards pc
WHERE pc.owner_id = (SELECT discord_id FROM public.players WHERE COALESCE(is_ai,false)=false LIMIT 1)
  AND COALESCE(pc.is_retired, false) = false
  AND COALESCE(pc.in_academy, false) = false
  AND NOT EXISTS (
      SELECT 1 FROM public.squad_assignments sa
      WHERE sa.discord_id = pc.owner_id AND sa.player_card_id = pc.id
  )
  AND NOT EXISTS (
      SELECT 1 FROM public.active_evolutions ae
      WHERE ae.owner_id = pc.owner_id AND ae.status = 'active' AND ae.card_id = pc.id
  )
  AND NOT EXISTS (
      SELECT 1 FROM public.active_training at
      WHERE at.club_id = pc.owner_id AND at.card_id = pc.id
  )
  AND NOT EXISTS (
      SELECT 1 FROM public.transfer_listings tl
      WHERE tl.seller_id = pc.owner_id AND tl.status = 'active' AND tl.card_id = pc.id
  )
ORDER BY pc.overall DESC;
""",
    "hub_listing_count": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT COUNT(*)::int
FROM public.transfer_listings
WHERE seller_id = (SELECT discord_id FROM public.players WHERE COALESCE(is_ai,false)=false LIMIT 1)
  AND status = 'active';
""",
    "skills_roster": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT c.id, c.name, c.overall, COALESCE(c.in_academy, false)
FROM public.player_cards c
WHERE c.owner_id = (SELECT discord_id FROM public.players WHERE COALESCE(is_ai,false)=false LIMIT 1)
  AND COALESCE(c.in_academy, false) = false
ORDER BY c.overall DESC;
""",
    "mentor_targets": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT c.id, c.name, c.overall, c.potential, c.level
FROM public.player_cards c
WHERE c.owner_id = (SELECT discord_id FROM public.players WHERE COALESCE(is_ai,false)=false LIMIT 1)
  AND COALESCE(c.in_academy, false) = false
  AND c.overall < c.potential
  AND COALESCE(c.level, 1) < 100
  AND NOT EXISTS (
      SELECT 1 FROM public.transfer_listings tl
      WHERE tl.card_id = c.id AND tl.status = 'active'
  )
ORDER BY COALESCE(c.level, 1);
""",
    "pending_rewards_count": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT COUNT(*)::INTEGER
FROM public.pending_level_rewards pr
JOIN public.player_cards c ON c.id = pr.player_id
WHERE NOT pr.claimed
  AND c.owner_id = (SELECT discord_id FROM public.players WHERE COALESCE(is_ai,false)=false LIMIT 1);
""",
    "standings_participants": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT lp.id, lp.season_id, lp.division_tier
FROM public.league_participants lp
WHERE lp.season_id = (SELECT id FROM public.league_seasons ORDER BY created_at DESC NULLS LAST LIMIT 1);
""",
    "standings_played_fixtures": """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id, home_team_id, away_team_id, home_score, away_score
FROM public.league_fixtures
WHERE season_id = (SELECT id FROM public.league_seasons ORDER BY created_at DESC NULLS LAST LIMIT 1)
  AND is_played = true;
""",
}


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set — cannot EXPLAIN")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"{stamp}_050"

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(INDEX_DUMP)
            idx_rows = cur.fetchall()
            idx_text = "\n".join(f"{t}\t{i}\t{d}" for t, i, d in idx_rows)
            idx_path = OUT / f"{prefix}_indexes_before.txt"
            idx_path.write_text(idx_text, encoding="utf-8")
            print(f"Wrote {idx_path.name} ({len(idx_rows)} indexes)")

            summary_lines: list[str] = []
            for name, sql in QUERIES.items():
                try:
                    cur.execute(sql)
                    rows = cur.fetchall()
                    text = "\n".join(r[0] for r in rows)
                    # pull planning/execution time lines
                    timing = [
                        ln for ln in text.splitlines()
                        if "Seq Scan" in ln or "Index" in ln or "Sort" in ln
                        or "Planning" in ln or "Execution" in ln or "rows=" in ln[:80]
                    ]
                    summary_lines.append(f"## {name}\n" + "\n".join(timing[:20]) + "\n")
                except Exception as exc:
                    text = f"ERROR: {exc}"
                    summary_lines.append(f"## {name}\nERROR: {exc}\n")
                    conn.rollback()
                path = OUT / f"{prefix}_{name}.txt"
                path.write_text(text, encoding="utf-8")
                print(f"Wrote {path.name}")

            summary_path = OUT / f"{prefix}_SUMMARY.txt"
            summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
            print(f"Wrote {summary_path.name}")


if __name__ == "__main__":
    main()
