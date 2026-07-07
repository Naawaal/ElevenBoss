#!/usr/bin/env python3
"""US-27 T27.12 — live DB smoke for league economy RPCs (psycopg)."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_DEBUG_LOG = Path(__file__).resolve().parents[1] / "debug-74c668.log"
_SESSION = "74c668"
_RUN = "t27-smoke"

# Isolated test IDs (negative — unlikely to collide with real Discord users)
TEST_GUILD = -880_270_001
TEST_PLAYER_A = -880_270_101
TEST_PLAYER_B = -880_270_102
TEST_PLAYER_POOR = -880_270_103


def _log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    entry = {
        "sessionId": _SESSION,
        "runId": _RUN,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    # #endregion


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _cfg_int(cur, key: str, default: int) -> int:
    cur.execute("SELECT public.get_game_config_int(%s, %s)", (key, default))
    return int(cur.fetchone()[0])


def _cleanup(cur, season_id: str | None, league_id: str | None) -> None:
    if season_id:
        cur.execute("DELETE FROM public.league_seasons WHERE id = %s", (season_id,))
    if league_id:
        cur.execute("DELETE FROM public.leagues WHERE id = %s", (league_id,))
    for pid in (TEST_PLAYER_A, TEST_PLAYER_B, TEST_PLAYER_POOR):
        cur.execute("DELETE FROM public.economy_ledger WHERE club_id = %s", (pid,))
        cur.execute("DELETE FROM public.players WHERE discord_id = %s", (pid,))
    cur.execute("DELETE FROM public.guild_config WHERE guild_id = %s", (TEST_GUILD,))


def main() -> int:
    import psycopg
    from economy.flows import league_match_coins_for_result, EconomyConfig

    cfg = EconomyConfig()
    manual_win = league_match_coins_for_result("win", "Grassroots", auto_sim=False, cfg=cfg)
    auto_win = league_match_coins_for_result("win", "Grassroots", auto_sim=True, cfg=cfg)
    _log("H3", "smoke:coins", "pure auto-sim mult", {"manual_win": manual_win, "auto_win": auto_win})
    if manual_win != 250 or auto_win != 125:
        print(f"FAIL coin mult: manual={manual_win} auto={auto_win}", file=sys.stderr)
        return 1

    dsn = _dsn()
    season_id: str | None = None
    league_id: str | None = None

    with psycopg.connect(dsn, autocommit=False) as conn:
        cur = conn.cursor()
        try:
            _cleanup(cur, None, None)

            cur.execute(
                "INSERT INTO public.guild_config (guild_id, league_status) VALUES (%s, 'inactive') "
                "ON CONFLICT (guild_id) DO NOTHING",
                (TEST_GUILD,),
            )

            old_enough = datetime.now(timezone.utc) - timedelta(days=30)
            for pid, coins, matches in (
                (TEST_PLAYER_A, 10_000, 15),
                (TEST_PLAYER_B, 10_000, 20),
                (TEST_PLAYER_POOR, 50, 15),
            ):
                cur.execute(
                    """
                    INSERT INTO public.players (
                        discord_id, username, club_name, manager_name, coins, matches_played, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (discord_id) DO UPDATE SET
                        coins = EXCLUDED.coins,
                        matches_played = EXCLUDED.matches_played,
                        created_at = EXCLUDED.created_at
                    """,
                    (pid, f"t27_{abs(pid)}", f"T27 FC {abs(pid)}", "Smoke", coins, matches, old_enough),
                )

            cur.execute(
                "INSERT INTO public.leagues (guild_id, name) VALUES (%s, %s) RETURNING id",
                (TEST_GUILD, "T27 Smoke League"),
            )
            league_id = str(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO public.league_seasons (
                    league_id, season_number, status, current_matchday, total_matchdays,
                    duration_days, config_json
                ) VALUES (%s, 99927, 'active', 1, 2, 7, %s::jsonb) RETURNING id
                """,
                (league_id, json.dumps({"entry_fee_coins": 1500, "max_clubs": 8})),
            )
            season_id = str(cur.fetchone()[0])

            for pid in (TEST_PLAYER_A, TEST_PLAYER_B, TEST_PLAYER_POOR):
                cur.execute(
                    "INSERT INTO public.league_participants (season_id, player_id) VALUES (%s, %s)",
                    (season_id, pid),
                )

            cur.execute("SELECT public.charge_league_entry_fees(%s::uuid)", (season_id,))
            fee_result = cur.fetchone()[0]
            _log("H1", "smoke:charge", "charge_league_entry_fees result", fee_result)

            charged = fee_result.get("charged") or []
            skipped = fee_result.get("skipped") or []
            if len(charged) != 2:
                raise AssertionError(f"expected 2 charged, got {len(charged)}: {charged}")
            if len(skipped) != 1 or skipped[0].get("reason") != "insufficient_coins":
                raise AssertionError(f"expected 1 insufficient_coins skip, got {skipped}")

            cur.execute(
                "SELECT COUNT(*) FROM public.league_participants WHERE season_id = %s",
                (season_id,),
            )
            if cur.fetchone()[0] != 2:
                raise AssertionError("poor player should be removed from participants")

            entry_fee = _cfg_int(cur, "league_entry_fee_coins", 1500)
            for pid in (TEST_PLAYER_A, TEST_PLAYER_B):
                cur.execute(
                    "SELECT entry_fee_paid, coins FROM public.league_participants lp "
                    "JOIN public.players p ON p.discord_id = lp.player_id "
                    "WHERE lp.season_id = %s AND lp.player_id = %s",
                    (season_id, pid),
                )
                paid, coins = cur.fetchone()
                if paid != entry_fee:
                    raise AssertionError(f"player {pid} entry_fee_paid={paid} expected {entry_fee}")
                if coins != 10_000 - entry_fee:
                    raise AssertionError(f"player {pid} coins={coins} expected {10000 - entry_fee}")

            cur.execute(
                "SELECT COUNT(*) FROM public.economy_ledger "
                "WHERE source = 'league_entry' AND club_id IN (%s, %s)",
                (TEST_PLAYER_A, TEST_PLAYER_B),
            )
            if cur.fetchone()[0] < 2:
                raise AssertionError("league_entry ledger rows missing")

            # Join gate config (H2)
            min_matches = _cfg_int(cur, "league_join_min_matches", 10)
            min_days = _cfg_int(cur, "league_join_min_account_days", 7)
            _log("H2", "smoke:join_gate", "config limits", {"min_matches": min_matches, "min_days": min_days})
            if min_matches != 10 or min_days != 7:
                raise AssertionError(f"join gate config wrong: {min_matches}/{min_days}")

            cur.execute("SELECT public.distribute_season_prizes(%s::uuid)", (season_id,))
            prize_result = cur.fetchone()[0]
            refunds = prize_result.get("refunds") or []
            _log("H4", "smoke:prizes", "distribute_season_prizes", prize_result)

            if len(refunds) != 2:
                raise AssertionError(f"expected 2 refunds, got {refunds}")

            for pid in (TEST_PLAYER_A, TEST_PLAYER_B):
                cur.execute(
                    "SELECT coins FROM public.players WHERE discord_id = %s", (pid,)
                )
                coins_after = cur.fetchone()[0]
                # net: -entry + prize + refund; prize varies by position
                if coins_after < 10_000:
                    raise AssertionError(f"player {pid} coins {coins_after} below start after refund")

                cur.execute(
                    "SELECT COUNT(*) FROM public.economy_ledger "
                    "WHERE source = 'league_entry_refund' AND club_id = %s",
                    (pid,),
                )
                if cur.fetchone()[0] != 1:
                    raise AssertionError(f"refund ledger missing for {pid}")

            conn.commit()
            _log("H5", "smoke:done", "all checks passed", {"season_id": season_id})
            print("T27.12 smoke PASSED")
            print(f"  charged={len(charged)} skipped={len(skipped)} refunds={len(refunds)}")
            print(f"  manual_win={manual_win} auto_win={auto_win}")
            return 0
        except Exception as exc:
            conn.rollback()
            _log("H0", "smoke:error", str(exc), {"season_id": season_id})
            print(f"T27.12 smoke FAILED: {exc}", file=sys.stderr)
            return 1
        finally:
            try:
                _cleanup(cur, season_id, league_id)
                conn.commit()
            except Exception:
                conn.rollback()


if __name__ == "__main__":
    raise SystemExit(main())
