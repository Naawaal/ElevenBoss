"""Ops helper for Match Engine V3 rollout / 050 US7 soak.

Usage:
  python scratch/ops_match_v3_rollout.py status
  python scratch/ops_match_v3_rollout.py soak-report [--days N]
  python scratch/ops_match_v3_rollout.py stage1-bot      # bot=1 only (forces friendly/league=0)
  python scratch/ops_match_v3_rollout.py stage2-friendly # requires bot=1; sets friendly=1
  python scratch/ops_match_v3_rollout.py stage3-league   # requires bot=1 + soak gate; sets league=1
  python scratch/ops_match_v3_rollout.py enable-bot      # legacy alias → stage1-bot
  python scratch/ops_match_v3_rollout.py rollback-mode bot|friendly|league
  python scratch/ops_match_v3_rollout.py rollback-drill
  python scratch/ops_match_v3_rollout.py disable-league

Does not delete V2 code. Does not change resolve_engine_version defaults (T052).
After any flag flip: restart bot or wait ~300s config TTL.
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
SOAK_MIN_FRIENDLY = 10
SOAK_MIN_LEAGUE = 10


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
    stage = 0
    if flags[FLAG_BOT] == 1:
        stage = 1
    if flags[FLAG_BOT] == 1 and flags[FLAG_FRIENDLY] == 1:
        stage = 2
    if flags[FLAG_BOT] == 1 and flags[FLAG_FRIENDLY] == 1 and flags[FLAG_LEAGUE] == 1:
        stage = 3
    print(f"=== staged soak level: Stage {stage}/3 ===")
    print("=== completed nss_v3 runs (all time) ===")
    print(f"  by_type: {soak['by_type'] or '{}'}")
    print(f"  bot_v3_completed: {soak['bot_v3_completed']} (stage3 gate >={SOAK_MIN_BOT})")
    print("=== recent bot match_runs ===")
    for row in soak["recent_bot"]:
        print(f"  {row[0][:8]}… type={row[1]} engine={row[2]} status={row[3]} at={row[4]}")
    gate_ok = soak["bot_v3_completed"] >= SOAK_MIN_BOT and flags[FLAG_BOT] == 1
    print(f"=== league enable gate: {'PASS' if gate_ok else 'BLOCKED'} ===")
    print("V2 remains executable for rollback (set flag=0). Do not delete V2 until T054.")


def cmd_soak_report(cur, days: int = 14) -> None:
    """Per-mode completion / failure / duration / score snapshot for US7 exit review."""
    flags = _get_flags(cur)
    print(f"=== soak-report last {days}d (flags bot={flags[FLAG_BOT]} "
          f"friendly={flags[FLAG_FRIENDLY]} league={flags[FLAG_LEAGUE]}) ===")
    cur.execute(
        """
        SELECT
          run_type,
          engine_version,
          status,
          COUNT(*)::int AS n,
          ROUND(AVG(EXTRACT(EPOCH FROM (COALESCE(completed_at, updated_at) - started_at)))::numeric, 1)
            AS avg_duration_s,
          ROUND(AVG(home_score + away_score)::numeric, 2) AS avg_goals,
          COUNT(*) FILTER (
            WHERE status IN ('streaming', 'completing')
          )::int AS in_flight
        FROM public.match_runs
        WHERE started_at >= NOW() - (%s || ' days')::interval
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
        """,
        (str(int(days)),),
    )
    rows = cur.fetchall()
    if not rows:
        print("  (no runs in window)")
    for run_type, engine, status, n, avg_s, avg_g, _inf in rows:
        print(
            f"  {run_type:8} {engine:6} {status:10} n={n:4} "
            f"avg_dur_s={avg_s} avg_goals={avg_g}"
        )

    print("=== completion rate by type×engine (window) ===")
    cur.execute(
        """
        SELECT
          run_type,
          engine_version,
          COUNT(*) FILTER (WHERE status = 'completed')::int AS completed,
          COUNT(*) FILTER (WHERE status = 'failed')::int AS failed,
          COUNT(*) FILTER (WHERE status = 'abandoned')::int AS abandoned,
          COUNT(*) FILTER (WHERE status IN ('streaming', 'completing'))::int AS active,
          COUNT(*)::int AS total
        FROM public.match_runs
        WHERE started_at >= NOW() - (%s || ' days')::interval
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        (str(int(days)),),
    )
    for run_type, engine, completed, failed, abandoned, active, total in cur.fetchall():
        rate = (100.0 * completed / total) if total else 0.0
        print(
            f"  {run_type:8} {engine:6} completed={completed}/{total} ({rate:.1f}%) "
            f"failed={failed} abandoned={abandoned} active={active}"
        )

    print("=== recoverable / in-flight (any age) ===")
    cur.execute(
        """
        SELECT run_type, engine_version, status, COUNT(*)::int
        FROM public.match_runs
        WHERE status IN ('streaming', 'completing', 'failed')
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
        """
    )
    inflight = cur.fetchall()
    if not inflight:
        print("  none")
    for row in inflight:
        print(f"  {row}")

    print("=== score distribution completed nss_v3 (window) ===")
    cur.execute(
        """
        SELECT
          run_type,
          COUNT(*)::int,
          ROUND(AVG(home_score)::numeric, 2),
          ROUND(AVG(away_score)::numeric, 2),
          ROUND(AVG(home_score + away_score)::numeric, 2),
          MIN(home_score + away_score),
          MAX(home_score + away_score)
        FROM public.match_runs
        WHERE status = 'completed'
          AND engine_version = 'nss_v3'
          AND started_at >= NOW() - (%s || ' days')::interval
        GROUP BY 1
        ORDER BY 1
        """,
        (str(int(days)),),
    )
    for row in cur.fetchall():
        print(
            f"  {row[0]:8} n={row[1]} avg_h={row[2]} avg_a={row[3]} "
            f"avg_total={row[4]} min_total={row[5]} max_total={row[6]}"
        )

    print("=== exit checklist (manual + this report) ===")
    print("  [ ] All three V3 modes enabled (flags=1)")
    print("  [ ] No integrity/settlement regressions (coins/XP/fatigue)")
    print("  [ ] No unresolved V3 recovery bugs (failed/stuck streaming)")
    print("  [ ] No meaningful latency regression (/admin Performance)")
    print("  [ ] No rollback needed for agreed soak window")
    print("  Then T052 default flip — separate deploy. Still keep V2 code until T054.")


def cmd_stage1_bot(cur) -> None:
    _set_flag(cur, FLAG_BOT, 1)
    _set_flag(cur, FLAG_FRIENDLY, 0)
    _set_flag(cur, FLAG_LEAGUE, 0)
    flags = _get_flags(cur)
    assert flags == {FLAG_BOT: 1, FLAG_FRIENDLY: 0, FLAG_LEAGUE: 0}
    print("Stage 1 OK: bot=1; friendly=0; league=0")
    print("Restart Discord bot (or wait config TTL) then smoke /battle bot matches.")


def cmd_stage2_friendly(cur) -> None:
    flags = _get_flags(cur)
    if flags[FLAG_BOT] != 1:
        raise SystemExit("Refuse stage2: match_engine_v3_bot must be 1")
    _set_flag(cur, FLAG_FRIENDLY, 1)
    flags = _get_flags(cur)
    assert flags[FLAG_FRIENDLY] == 1
    print(f"Stage 2 OK: friendly=1 (bot={flags[FLAG_BOT]}, league={flags[FLAG_LEAGUE]})")
    print("Restart bot / wait TTL; smoke one friendly (sandbox economy unchanged).")


def cmd_stage3_league(cur) -> None:
    soak = _soak_counts(cur)
    flags = _get_flags(cur)
    force = "--force" in sys.argv
    if flags[FLAG_BOT] != 1:
        raise SystemExit("Refuse stage3: bot flag is not on")
    if soak["bot_v3_completed"] < SOAK_MIN_BOT and not force:
        raise SystemExit(
            f"Refuse stage3: bot_v3_completed={soak['bot_v3_completed']} "
            f"< {SOAK_MIN_BOT} (pass --force to override)"
        )
    _set_flag(cur, FLAG_LEAGUE, 1)
    flags = _get_flags(cur)
    assert flags[FLAG_LEAGUE] == 1
    print("Stage 3 OK: league=1 — V2 code still present for rollback")
    print("Restart bot / wait TTL; smoke live Play + auto-sim settlement.")


def cmd_rollback_mode(cur, mode: str) -> None:
    key = {
        "bot": FLAG_BOT,
        "friendly": FLAG_FRIENDLY,
        "league": FLAG_LEAGUE,
    }.get(mode)
    if not key:
        raise SystemExit("rollback-mode expects bot|friendly|league")
    _set_flag(cur, key, 0)
    print(f"Rollback OK: {key}=0 — new kicks use nss_v2; in-flight nss_v3 finish on V3")


def cmd_rollback_drill(cur) -> None:
    _set_flag(cur, FLAG_BOT, 0)
    print("rollback-drill step1: bot=0")
    _set_flag(cur, FLAG_BOT, 1)
    print("rollback-drill step2: bot=1 restored (friendly/league unchanged)")


def cmd_disable_league(cur) -> None:
    _set_flag(cur, FLAG_LEAGUE, 0)
    print("OK: match_engine_v3_league=0")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1].strip().lower()
    days = 14
    if "--days" in sys.argv:
        i = sys.argv.index("--days")
        days = int(sys.argv[i + 1])

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            if cmd == "status":
                cmd_status(cur)
            elif cmd == "soak-report":
                cmd_soak_report(cur, days=days)
            elif cmd in ("stage1-bot", "enable-bot"):
                cmd_stage1_bot(cur)
                conn.commit()
            elif cmd == "stage2-friendly":
                cmd_stage2_friendly(cur)
                conn.commit()
            elif cmd == "stage3-league":
                cmd_stage3_league(cur)
                conn.commit()
            elif cmd == "rollback-mode":
                if len(sys.argv) < 3:
                    raise SystemExit("rollback-mode requires bot|friendly|league")
                cmd_rollback_mode(cur, sys.argv[2].strip().lower())
                conn.commit()
            elif cmd == "rollback-drill":
                cmd_rollback_drill(cur)
                conn.commit()
            elif cmd == "disable-league":
                cmd_disable_league(cur)
                conn.commit()
            elif cmd == "enable-league":
                # legacy name → stage3
                cmd_stage3_league(cur)
                conn.commit()
            else:
                raise SystemExit(f"Unknown command {cmd!r}\n{__doc__}")
    print(f"done at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
