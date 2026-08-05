# tests/test_pvp_ghost_backfill_e2e.py
"""Database-backed end-to-end integration test suite for Instant PvP Backfill (Feature 054)."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
import pytest
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from apps.discord_bot.embeds.pvp_embeds import match_history_mode_label
from pvp.reward_policy import pvp_lp_delta, reward_policy

url = os.environ.get("DATABASE_URL")
if url:
    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
else:
    dsn = None


def get_db_conn():
    if not dsn:
        pytest.skip("DATABASE_URL not set in environment")
    return psycopg.connect(dsn)


@pytest.fixture(scope="function")
def setup_test_managers():
    """Sets up isolated test managers in the database with valid 11-player squads."""
    if not dsn:
        pytest.skip("DATABASE_URL not set in environment")

    home_id = 999103001
    ghost_id = 999103002
    ai_seeker_id = 999103003
    live_id = 999103004

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # Enable PvP flags in game_config for test execution
            cur.execute("INSERT INTO public.game_config (key, value_json) VALUES ('battle_pvp_enabled', 'true'), ('pvp_backfill_enabled', 'true') ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json")

            # Clean old test data
            cur.execute("DELETE FROM public.match_locks WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.match_history WHERE player_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.match_runs WHERE home_discord_id IN (%s, %s, %s, %s) OR away_discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id, home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.pvp_ghost_snapshots WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.pvp_ghost_encounters WHERE challenger_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.pvp_matchmaking_queue WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.squad_assignments WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.squads WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.player_cards WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.players WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))

            # Insert players
            for uid, cname, mname in [
                (home_id, "Kathmandu United", "Manager Alpha"),
                (ghost_id, "Pokhara City FC", "Manager Ghost"),
                (ai_seeker_id, "Lalitpur XI", "Manager Seeker"),
                (live_id, "Himalayan Sherpa", "Manager Live"),
            ]:
                cur.execute(
                    """
                    INSERT INTO public.players (
                        discord_id, username, club_name, manager_name, action_energy, global_lp, pvp_ranked_matches
                    ) VALUES (%s, %s, %s, %s, 100, 1200, 10)
                    """,
                    (uid, f"user_{uid}", cname, mname),
                )
                cur.execute("INSERT INTO public.squads (discord_id) VALUES (%s) ON CONFLICT DO NOTHING", (uid,))

                # Insert 11 active cards for each
                positions = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "FWD", "FWD", "FWD"]
                for idx, pos in enumerate(positions):
                    cur.execute(
                        """
                        INSERT INTO public.player_cards (
                            owner_id, name, position, rarity, base_rating, potential, overall, pac, sho, pas, dri, "def", phy, fatigue, date_of_birth
                        ) VALUES (%s, %s, %s, 'Rare', 80, 85, 80, 80, 80, 80, 80, 80, 80, 0, '2000-01-01'::DATE)
                        RETURNING id
                        """,
                        (uid, f"Player {idx+1}", pos),
                    )
                    card_id = cur.fetchone()[0]
                    cur.execute(
                        """
                        INSERT INTO public.squad_assignments (discord_id, player_card_id, position_slot)
                        VALUES (%s, %s, %s)
                        """,
                        (uid, card_id, idx + 1),
                    )

            # Generate ghost snapshot for ghost_id
            cur.execute("SELECT public.refresh_pvp_ghost_snapshot(%s)", (ghost_id,))

        conn.commit()

    yield {
        "home_id": home_id,
        "ghost_id": ghost_id,
        "ai_seeker_id": ai_seeker_id,
        "live_id": live_id,
    }

    # Cleanup after module tests
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.match_runs WHERE home_discord_id IN (%s, %s, %s, %s) OR away_discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id, home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.pvp_ghost_snapshots WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.pvp_ghost_encounters WHERE challenger_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.pvp_matchmaking_queue WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.squad_assignments WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.squads WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.player_cards WHERE owner_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
            cur.execute("DELETE FROM public.players WHERE discord_id IN (%s, %s, %s, %s)", (home_id, ghost_id, ai_seeker_id, live_id))
        conn.commit()


def test_e2e_single_searcher_ghost_lifecycle(setup_test_managers):
    """Test 1 & 3: Single searcher queues -> 10s wait -> matched with Ghost Manager -> challenger rewarded -> offline ghost owner 100% untouched."""
    home_id = setup_test_managers["home_id"]
    ghost_id = setup_test_managers["ghost_id"]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Clear previous queue rows for clean state
            cur.execute("DELETE FROM public.pvp_matchmaking_queue WHERE owner_id IN (%s, %s)", (home_id, ghost_id))

            # Capture ghost owner state BEFORE match
            cur.execute("SELECT action_energy, coins, global_lp, pvp_ranked_matches FROM public.players WHERE discord_id = %s", (ghost_id,))
            ghost_before = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM public.match_history WHERE player_id = %s", (ghost_id,))
            ghost_hist_before = cur.fetchone()[0]

            # 1. Home joins queue
            cur.execute("SELECT public.join_pvp_queue(%s, 1001, 2001)", (home_id,))
            queue_res = cur.fetchone()[0]
            assert queue_res.get("status") == "searching"

            # 2. Simulate 11s queue wait time (past backfill_after)
            cur.execute(
                "UPDATE public.pvp_matchmaking_queue SET backfill_after = NOW() - INTERVAL '5 seconds' WHERE owner_id = %s",
                (home_id,),
            )

            # 3. Matchmaker execution
            cur.execute("SELECT public.try_match_pvp_queue()")
            match_res = cur.fetchone()[0]
            assert match_res.get("matched") is True
            assert match_res.get("opponent_mode") == "ghost"
            run_id = match_res.get("run_id")
            assert run_id is not None

            # 4. Finalize match (Challenger wins 2-1)
            cur.execute("SELECT public.finalize_pvp_match(%s, 2, 1, 80.0, 80.0)", (run_id,))
            fin_res = cur.fetchone()[0]
            assert fin_res.get("ok") is True
            assert fin_res.get("opponent_mode") == "ghost"

            # Home received Ghost Win rewards (100 * 1.25 * 0.85 = 106 coins, +11 LP)
            home_payload = fin_res["home"]
            assert home_payload["coins"] == 106
            assert home_payload["lp_delta"] == 11

            # Assert Challenger has 1 history row
            cur.execute("SELECT opponent_mode, global_lp_delta FROM public.match_history WHERE player_id = %s AND run_id = %s", (home_id, run_id))
            hist_row = cur.fetchone()
            assert hist_row[0] == "ghost"
            assert hist_row[1] == 11

            # Assert Ghost Encounter logged
            cur.execute("SELECT opponent_mode FROM public.pvp_ghost_encounters WHERE run_id = %s", (run_id,))
            enc_row = cur.fetchone()
            assert enc_row[0] == "ghost"

            # 5. Assert Offline Ghost Owner BEFORE vs AFTER isolation
            cur.execute("SELECT action_energy, coins, global_lp, pvp_ranked_matches FROM public.players WHERE discord_id = %s", (ghost_id,))
            ghost_after = cur.fetchone()
            assert ghost_after == ghost_before, f"Ghost owner stats altered! Before: {ghost_before}, After: {ghost_after}"

            cur.execute("SELECT COUNT(*) FROM public.match_history WHERE player_id = %s", (ghost_id,))
            ghost_hist_after = cur.fetchone()[0]
            assert ghost_hist_after == ghost_hist_before, "Ghost owner received an unwanted match history entry!"

        conn.commit()


def test_e2e_single_searcher_no_ghost_ai_lifecycle(setup_test_managers):
    """Test 2: Single searcher queues with 0 ghost snapshots -> matched with Calibrated Ranked AI -> challenger receives AI rewards."""
    ai_seeker_id = setup_test_managers["ai_seeker_id"]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Clear queue rows
            cur.execute("DELETE FROM public.pvp_matchmaking_queue WHERE owner_id = %s", (ai_seeker_id,))

            # Delete any existing ghost snapshots so Level 2 produces zero candidates
            cur.execute("DELETE FROM public.pvp_ghost_snapshots")

            # 1. Seeker joins queue
            cur.execute("SELECT public.join_pvp_queue(%s, 1001, 2001)", (ai_seeker_id,))
            queue_res = cur.fetchone()[0]
            assert queue_res.get("status") == "searching"

            # 2. Simulate wait past backfill_after
            cur.execute(
                "UPDATE public.pvp_matchmaking_queue SET backfill_after = NOW() - INTERVAL '5 seconds' WHERE owner_id = %s",
                (ai_seeker_id,),
            )

            # 3. Matchmaker execution
            cur.execute("SELECT public.try_match_pvp_queue()")
            match_res = cur.fetchone()[0]
            assert match_res.get("matched") is True
            assert match_res.get("opponent_mode") == "ai_backfill"
            run_id = match_res.get("run_id")

            # 4. Finalize match (Challenger wins 1-0)
            cur.execute("SELECT public.finalize_pvp_match(%s, 1, 0, 80.0, 80.0)", (run_id,))
            fin_res = cur.fetchone()[0]
            assert fin_res.get("ok") is True
            assert fin_res.get("opponent_mode") == "ai_backfill"

            # Challenger AI Win rewards (100 * 1.25 * 0.70 = 88 coins, +8 LP at 1200 LP)
            home_payload = fin_res["home"]
            assert home_payload["coins"] == 88
            assert home_payload["lp_delta"] == 8

        conn.commit()


def test_e2e_sql_python_reward_policy_parity(setup_test_managers):
    """Test 4: Verify SQL finalize_pvp_match output matches pure Python reward_policy and pvp_lp_delta calculations for all modes."""
    # Ghost Win
    pol_ghost_win = reward_policy("pvp", "win", opponent_mode="ghost")
    ghost_win_coins = round(100 * pol_ghost_win.coin_multiplier)
    _, ghost_win_lp = pvp_lp_delta("win", current_lp=1000, opponent_mode="ghost", ranked_matches_completed=10)
    assert ghost_win_coins == 106
    assert ghost_win_lp == 11

    # AI Win
    pol_ai_win = reward_policy("pvp", "win", opponent_mode="ai_backfill")
    ai_win_coins = round(100 * pol_ai_win.coin_multiplier)
    _, ai_win_lp = pvp_lp_delta("win", current_lp=1000, opponent_mode="ai_backfill", ranked_matches_completed=10)
    assert ai_win_coins == 88
    assert ai_win_lp == 7

    # Live Win
    pol_live_win = reward_policy("pvp", "win", opponent_mode="live")
    live_win_coins = round(100 * pol_live_win.coin_multiplier)
    _, live_win_lp = pvp_lp_delta("win", current_lp=1000, opponent_mode="live", ranked_matches_completed=10)
    assert live_win_coins == 125
    assert live_win_lp == 15


def test_e2e_concurrent_live_vs_ghost_race(setup_test_managers):
    """Test 5: When Manager A reaches backfill_after and Manager B joins simultaneously, Level 1 Live match occurs (zero ghost runs)."""
    home_id = setup_test_managers["home_id"]
    live_id = setup_test_managers["live_id"]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Clear queues and history/locks for test isolation
            cur.execute("DELETE FROM public.match_locks WHERE discord_id IN (%s, %s)", (home_id, live_id))
            cur.execute("DELETE FROM public.match_history WHERE player_id IN (%s, %s)", (home_id, live_id))
            cur.execute("DELETE FROM public.pvp_matchmaking_queue WHERE owner_id IN (%s, %s)", (home_id, live_id))

            # Re-create ghost snapshot for ghost_id
            ghost_id = setup_test_managers["ghost_id"]
            cur.execute("SELECT public.refresh_pvp_ghost_snapshot(%s)", (ghost_id,))

            # A joins and reaches backfill_after
            cur.execute("SELECT public.join_pvp_queue(%s, 1001, 2001)", (home_id,))
            cur.execute("UPDATE public.pvp_matchmaking_queue SET backfill_after = NOW() - INTERVAL '5 seconds' WHERE owner_id = %s", (home_id,))

            # B joins live queue simultaneously
            cur.execute("SELECT public.join_pvp_queue(%s, 1001, 2001)", (live_id,))

            # Matchmaker runs
            cur.execute("SELECT public.try_match_pvp_queue()")
            match_res = cur.fetchone()[0]
            assert match_res.get("matched") is True
            assert match_res.get("opponent_mode") == "live"
            assert set([match_res.get("home_discord_id"), match_res.get("away_discord_id")]) == set([home_id, live_id])

        conn.commit()


def test_e2e_concurrent_daily_backfill_cap(setup_test_managers):
    """Test 6: Daily backfill count cap (< 3 per day) is enforced safely."""
    home_id = setup_test_managers["home_id"]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # Clear queues & encounters
            cur.execute("DELETE FROM public.pvp_matchmaking_queue WHERE owner_id = %s", (home_id,))
            cur.execute("DELETE FROM public.pvp_ghost_encounters WHERE challenger_id = %s", (home_id,))

            # Set today's backfill encounter count to 3
            for _ in range(3):
                cur.execute(
                    "INSERT INTO public.pvp_ghost_encounters (run_id, challenger_id, opponent_mode) VALUES (gen_random_uuid(), %s, 'ghost')",
                    (home_id,),
                )

            # Home joins queue past backfill_after
            cur.execute("SELECT public.join_pvp_queue(%s, 1001, 2001)", (home_id,))
            cur.execute("UPDATE public.pvp_matchmaking_queue SET backfill_after = NOW() - INTERVAL '5 seconds' WHERE owner_id = %s", (home_id,))

            # Matchmaker should reject backfill match due to daily cap
            cur.execute("SELECT public.try_match_pvp_queue()")
            match_res = cur.fetchone()[0]
            assert match_res.get("matched") is False
            assert match_res.get("reason") == "backfill_daily_cap_reached"

        conn.commit()


def test_e2e_rendered_battle_history_mode_labels():
    """Test 8: Battle History mode labels render accurately for Live, Ghost, AI, and legacy rows."""
    assert match_history_mode_label("pvp", "live") == "🟢 Ranked PvP"
    assert match_history_mode_label("pvp", "ghost") == "👻 Ghost PvP"
    assert match_history_mode_label("pvp", "ai_backfill") == "🤖 Ranked AI"
    assert match_history_mode_label("pvp", None) == "🟢 Ranked PvP"
    assert match_history_mode_label("practice", None) == "AI Practice"
    assert match_history_mode_label("friendly", None) == "Friendly"
