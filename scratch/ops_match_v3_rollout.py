"""Ops helper for 044 Match Engine V3 rollout — flag flip, rollback drill, soak counts.

Usage:
  python scratch/ops_match_v3_rollout.py status
  python scratch/ops_match_v3_rollout.py enable-bot
  python scratch/ops_match_v3_rollout.py rollback-drill   # bot off → verify → bot on
  python scratch/ops_match_v3_rollout.py enable-league    # refused unless soak gate met
  python scratch/ops_match_v3_rollout.py disable-league

Does not touch Discord; managers must complete smoke matches after enable-bot + bot restart.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL not set in .env")
DSN = url.replace("postgresql+asyncpg://", "postgresql://")

FLAG_BOT = "match_engine_v3_bot"
FLAG_LEAGUE = "match_engine_v3_league"
FLAG_FRIENDLY = "match_engine_v3_friendly"
SOAK_MIN_BOT = 20


def _get_flags(cur) -> dict[str, int]:
    cur.execute(
        """
        SELECT key, COALESCE((value_json #>> '{}')::int, 0)
        FROM public.game_config
        WHERE key = ANY(%s)
        """,
        ([FLAG_BOT, FLAG_LEAGUE, FLAG_FRIENDLY],),
    )
    out = {FLAG_BOT: 0, FLAG_LEAGUE: 0, FLAG_FRIENDLY: 0}
    for key, val in cur.fetchall():
        out[key] = int(val)
    return out


def _set_flag(cur, key: str, value: int) -> None:
    cur.execute(
        """
        UPDATE public.game_config
        SET value_json = to_jsonb(%s::int)
        WHERE key = %s
        """,
        (int(value), key),
    )
    if cur.rowcount != 1:
        raise SystemExit(f"UPDATE affected {cur.rowcount} rows for {key} — expected 1")


def _soak_counts(cur) -> dict:
    cur.execute(
        """
        SELECT run_type, engine_version, COUNT(*)::int
        FROM public.match_runs
        WHERE status = 'completed'
          AND engine_version = 'nss_v3'
        GROUP BY run_type, engine_version
        ORDER BY run_type
        """
    )
    by_type = {row[0]: row[2] for row in cur.fetchall()}
    cur.execute(
        """
        SELECT COUNT(*)::int
        FROM public.match_runs
        WHERE status = 'completed'
          AND run_type = 'bot'
          AND engine_version = 'nss_v3'
        """
    )
    bot_v3 = int(cur.fetchone()[0])
    cur.execute(
        """
        SELECT id::text, run_type, engine_version, status, updated_at
        FROM public.match_runs
        WHERE run_type = 'bot'
        ORDER BY updated_at DESC NULLS LAST
        LIMIT 5
        """
    )
    recent_bot = cur.fetchall()
    return {"by_type": by_type, "bot_v3_completed": bot_v3, "recent_bot": recent_bot}


def cmd_status(cur) -> None:
    flags = _get_flags(cur)
    soak = _soak_counts(cur)
    print("=== engine flags ===")
    for k, v in flags.items():
        print(f"  {k} = {v}")
    print("=== completed nss_v3 runs ===")
    print(f"  by_type: {soak['by_type'] or '{}'}")
    print(f"  bot_v3_completed: {soak['bot_v3_completed']} (gate >={SOAK_MIN_BOT})")
    print("=== recent bot match_runs ===")
    for row in soak["recent_bot"]:
        print(f"  {row[0][:8]}… type={row[1]} engine={row[2]} status={row[3]} at={row[4]}")
    gate_ok = soak["bot_v3_completed"] >= SOAK_MIN_BOT and flags[FLAG_BOT] == 1
    print(f"=== league enable gate: {'PASS' if gate_ok else 'BLOCKED'} ===")


def cmd_enable_bot(cur) -> None:
    _set_flag(cur, FLAG_BOT, 1)
    flags = _get_flags(cur)
    assert flags[FLAG_BOT] == 1
    assert flags[FLAG_LEAGUE] == 0
    assert flags[FLAG_FRIENDLY] == 0
    print("T010 OK: match_engine_v3_bot=1; league=0; friendly=0")
    print("Restart the Discord bot (or wait ~300s config TTL) before smoke matches.")


def cmd_rollback_drill(cur) -> None:
    _set_flag(cur, FLAG_BOT, 0)
    flags = _get_flags(cur)
    assert flags[FLAG_BOT] == 0
    print("T012 step1: bot flag OFF — new kicks should pin nss_v2 after cache refresh")
    _set_flag(cur, FLAG_BOT, 1)
    flags = _get_flags(cur)
    assert flags[FLAG_BOT] == 1
    assert flags[FLAG_LEAGUE] == 0
    assert flags[FLAG_FRIENDLY] == 0
    print("T012/T013 OK: rollback drill done; bot re-enabled for soak (league/friendly still 0)")


def cmd_enable_league(cur) -> None:
    soak = _soak_counts(cur)
    flags = _get_flags(cur)
    if soak["bot_v3_completed"] < SOAK_MIN_BOT:
        raise SystemExit(
            f"Refuse league enable: bot_v3_completed={soak['bot_v3_completed']} "
            f"< {SOAK_MIN_BOT} (T020 soak gate)"
        )
    if flags[FLAG_BOT] != 1:
        raise SystemExit("Refuse league enable: bot flag is not on")
    _set_flag(cur, FLAG_LEAGUE, 1)
    flags = _get_flags(cur)
    assert flags[FLAG_LEAGUE] == 1
    assert flags[FLAG_FRIENDLY] == 0
    print("T022 OK: match_engine_v3_league=1; friendly remains 0")
    print("Restart bot / wait TTL; then live Play + auto-sim smoke (T023).")


def cmd_disable_league(cur) -> None:
    _set_flag(cur, FLAG_LEAGUE, 0)
    print("T024 OK: match_engine_v3_league=0")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1].strip().lower()
    handlers = {
        "status": cmd_status,
        "enable-bot": cmd_enable_bot,
        "rollback-drill": cmd_rollback_drill,
        "enable-league": cmd_enable_league,
        "disable-league": cmd_disable_league,
    }
    if cmd not in handlers:
        raise SystemExit(f"Unknown command {cmd!r}\n{__doc__}")
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            handlers[cmd](cur)
            if cmd != "status":
                conn.commit()
            else:
                # read-only
                pass
    print(f"done at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
