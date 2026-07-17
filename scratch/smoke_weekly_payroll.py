"""Live RPC smoke for weekly payroll (019).

Usage:
  python scratch/smoke_weekly_payroll.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set")
dsn = url.replace("postgresql+asyncpg://", "postgresql://")


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().strip('"').lower() == "true"


def main() -> None:
    keep = os.environ.get("SMOKE_KEEP_FLAG") == "1"
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value_json FROM public.game_config WHERE key = 'wages_payroll_enabled'"
            )
            row = cur.fetchone()
            prior = _as_bool(row[0] if row else False)

            # --- Flag off: no coin change ---
            cur.execute(
                """
                INSERT INTO public.game_config (key, value_json)
                VALUES ('wages_payroll_enabled', 'false')
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            )
            conn.commit()

            cur.execute(
                """
                SELECT discord_id, coins FROM public.players
                WHERE COALESCE(is_ai, FALSE) = FALSE
                ORDER BY discord_id LIMIT 1
                """
            )
            human = cur.fetchone()
            if not human:
                raise SystemExit("Need at least one human club")
            club_id, coins_before = int(human[0]), int(human[1])

            cur.execute(
                "SELECT public.process_club_weekly_payroll(%s, %s)",
                (club_id, "SMOKE-OFF"),
            )
            off = cur.fetchone()[0]
            conn.commit()
            if isinstance(off, str):
                off = json.loads(off)
            assert off.get("status") == "skipped_flag", off

            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (club_id,))
            assert int(cur.fetchone()[0]) == coins_before, "flag-off must not debit"

            # --- Null expiry backfill check ---
            cur.execute(
                "SELECT COUNT(*) FROM public.player_cards WHERE contract_expires_at IS NULL"
            )
            null_exp = int(cur.fetchone()[0])
            assert null_exp == 0, f"expected no null contract_expires_at, got {null_exp}"

            # --- AI exempt ---
            cur.execute(
                """
                SELECT discord_id, coins FROM public.players
                WHERE COALESCE(is_ai, FALSE) = TRUE
                ORDER BY discord_id LIMIT 1
                """
            )
            ai = cur.fetchone()
            if ai:
                ai_id, ai_coins = int(ai[0]), int(ai[1])
                cur.execute(
                    """
                    INSERT INTO public.game_config (key, value_json)
                    VALUES ('wages_payroll_enabled', 'true')
                    ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                    """
                )
                conn.commit()
                cur.execute(
                    "SELECT public.process_club_weekly_payroll(%s, %s)",
                    (ai_id, "SMOKE-AI"),
                )
                ai_res = cur.fetchone()[0]
                conn.commit()
                if isinstance(ai_res, str):
                    ai_res = json.loads(ai_res)
                assert ai_res.get("status") == "skipped_ai", ai_res
                cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (ai_id,))
                assert int(cur.fetchone()[0]) == ai_coins

            # --- Paid + idempotent ---
            cur.execute(
                """
                INSERT INTO public.game_config (key, value_json)
                VALUES ('wages_payroll_enabled', 'true')
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            )
            # Fresh week key unique to this run
            import time

            week = f"SMOKE-{int(time.time())}"
            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (club_id,))
            coins0 = int(cur.fetchone()[0])
            # Ensure club can pay — top up gently via economy pipe
            cur.execute(
                """
                SELECT public.apply_club_economy(
                    %s, 50000, 0, 'smoke_payroll_topup', %s, '{}'::jsonb
                )
                """,
                (club_id, f"smoke_topup:{week}"),
            )
            conn.commit()
            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (club_id,))
            coins1 = int(cur.fetchone()[0])

            cur.execute(
                "SELECT public.process_club_weekly_payroll(%s, %s)",
                (club_id, week),
            )
            first = cur.fetchone()[0]
            conn.commit()
            if isinstance(first, str):
                first = json.loads(first)
            assert first.get("status") in ("paid", "partial", "skipped_zero"), first
            paid = int(first.get("paid_coins") or 0)

            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (club_id,))
            coins2 = int(cur.fetchone()[0])
            assert coins2 == coins1 - paid, (coins1, coins2, paid, first)

            cur.execute(
                "SELECT public.process_club_weekly_payroll(%s, %s)",
                (club_id, week),
            )
            second = cur.fetchone()[0]
            conn.commit()
            if isinstance(second, str):
                second = json.loads(second)
            assert second.get("idempotent") is True or second.get("paid_coins") == paid
            cur.execute("SELECT coins FROM public.players WHERE discord_id = %s", (club_id,))
            coins3 = int(cur.fetchone()[0])
            assert coins3 == coins2, "second run must not debit again"

            print("smoke_weekly_payroll OK", json.dumps({
                "club_id": club_id,
                "week": week,
                "first": first,
                "second_idempotent": True,
                "null_expiries": null_exp,
            }, default=str))

            if not keep:
                cur.execute(
                    """
                    INSERT INTO public.game_config (key, value_json)
                    VALUES ('wages_payroll_enabled', %s)
                    ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                    """,
                    (json.dumps(prior),),
                )
                # Clean smoke payroll row + reverse top-up is optional; leave ledger as ops noise
                cur.execute(
                    "DELETE FROM public.payroll_runs WHERE club_id = %s AND week_key = %s",
                    (club_id, week),
                )
                conn.commit()
                print(f"Restored wages_payroll_enabled={prior}; deleted smoke payroll_runs row")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        raise
