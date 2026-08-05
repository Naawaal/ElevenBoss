"""Run E2E tests directly with verbose output."""
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

home_id = 999103001
ghost_id = 999103002
ai_seeker_id = 999103003
live_id = 999103004

print("Setting up test managers...")
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        # Clean
        cur.execute("DELETE FROM public.match_runs WHERE home_discord_id IN (%s, %s, %s, %s) OR away_discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id, home_id, ghost_id, ai_seeker_id, live_id))
        cur.execute("DELETE FROM public.pvp_ghost_snapshots WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
        cur.execute("DELETE FROM public.pvp_ghost_encounters WHERE challenger_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
        cur.execute("DELETE FROM public.pvp_matchmaking_queue WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
        cur.execute("DELETE FROM public.squad_assignments WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
        cur.execute("DELETE FROM public.squads WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
        cur.execute("DELETE FROM public.player_cards WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
        cur.execute("DELETE FROM public.players WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))

        # Insert players & squads
        for uid, cname, mname in [
            (home_id, "Kathmandu United", "Manager Alpha"),
            (ghost_id, "Pokhara City FC", "Manager Ghost"),
            (ai_seeker_id, "Lalitpur XI", "Manager Seeker"),
            (live_id, "Himalayan Sherpa", "Manager Live"),
        ]:
            cur.execute("INSERT INTO public.players (discord_id, username, club_name, manager_name, action_energy, global_lp, pvp_ranked_matches) VALUES (%s, %s, %s, %s, 100, 1200, 10)", (uid, f"user_{uid}", cname, mname))
            cur.execute("INSERT INTO public.squads (discord_id) VALUES (%s) ON CONFLICT DO NOTHING", (uid,))
            positions = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD", "FWD"]
            for idx, pos in enumerate(positions):
                cur.execute("INSERT INTO public.player_cards (owner_id, name, position, rarity, base_rating, potential, overall, pac, sho, pas, dri, \"def\", phy, fatigue, date_of_birth) VALUES (%s, %s, %s, 'Rare', 80, 85, 80, 80, 80, 80, 80, 80, 80, 0, '2000-01-01'::DATE) RETURNING id", (uid, f"Player {idx+1}", pos))
                cid = cur.fetchone()[0]
                cur.execute("INSERT INTO public.squad_assignments (discord_id, player_card_id, position_slot) VALUES (%s, %s, %s)", (uid, cid, idx + 1))

        # Generate snapshot for ghost manager
        cur.execute("SELECT public.refresh_pvp_ghost_snapshot(%s)", (ghost_id,))
        snap_res = cur.fetchone()[0]
        print("refresh_pvp_ghost_snapshot result:", snap_res)

    conn.commit()

print("Setup complete! Running E2E Ghost Match scenario...")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        # Join queue
        cur.execute("SELECT public.join_pvp_queue(%s, 1001, 2001)", (home_id,))
        print("join_pvp_queue:", cur.fetchone()[0])

        # Backfill threshold
        cur.execute("UPDATE public.pvp_matchmaking_queue SET backfill_after = NOW() - INTERVAL '5 seconds' WHERE owner_id = %s", (home_id,))

        # Try match
        cur.execute("SELECT public.try_match_pvp_queue()")
        m_res = cur.fetchone()[0]
        print("try_match_pvp_queue:", m_res)
        run_id = m_res.get("run_id")

        # Finalize match
        cur.execute("SELECT public.finalize_pvp_match(%s, 2, 1, 80.0, 80.0)", (run_id,))
        fin_res = cur.fetchone()[0]
        print("finalize_pvp_match:", fin_res)

    conn.commit()

print("E2E Direct Script PASS!")
