"""Feature 052 Phase 2 — live YA V2 DB/config/RPC parity checks."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
out = ROOT / "specs" / "052-youth-academy-v2-acceptance" / "evidence" / "db-snapshot.txt"

lines: list[str] = []

def log(msg: str) -> None:
    print(msg)
    lines.append(msg)

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        # Migration presence (schema objects from 095)
        cur.execute(
            """
            SELECT
              to_regprocedure('public.dispatch_academy_assessment(bigint,uuid,text)') IS NOT NULL,
              to_regprocedure('public.finalize_academy_assessment(bigint,uuid)') IS NOT NULL,
              to_regprocedure('public.ensure_academy_weekly_row(bigint)') IS NOT NULL,
              to_regclass('public.academy_weekly_actions') IS NOT NULL,
              to_regclass('public.academy_scout_assessments') IS NOT NULL,
              EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='public' AND table_name='player_cards'
                  AND column_name='pot_visible_lo'
              )
            """
        )
        row = cur.fetchone()
        log(f"095 objects present: assess={row[0]} finalize={row[1]} weekly={row[2]} "
            f"weekly_tbl={row[3]} assess_tbl={row[4]} pot_lo_col={row[5]}")

        cur.execute(
            """
            SELECT key, value_json::text
            FROM public.game_config
            WHERE key IN (
              'youth_academy_v2_enabled',
              'youth_academy_legendary_enabled',
              'youth_intake_count',
              'academy_weekly_promote_cap',
              'academy_weekly_paid_sign_cap',
              'academy_promote_fee',
              'academy_promote_first_free',
              'academy_age_warn',
              'academy_age_out',
              'academy_age_out_grace_hours',
              'scout_deep_min_range'
            )
            ORDER BY key
            """
        )
        log("--- game_config ---")
        for k, v in cur.fetchall():
            log(f"  {k} = {v}")

        cur.execute("SELECT lvl, public.academy_slot_cap(lvl) FROM generate_series(1,5) AS lvl")
        caps = list(cur.fetchall())
        log("--- academy_slot_cap ---")
        for lvl, cap in caps:
            log(f"  L{lvl} -> {cap}")
        expected = [3, 3, 4, 4, 5]
        ok_caps = [c for _, c in caps] == expected
        log(f"caps_match_expected={ok_caps}")

        # Illegal academy POT remaining
        cur.execute(
            """
            SELECT COUNT(*) FROM public.player_cards pc
            WHERE in_academy AND COALESCE(is_retired,false)=false
              AND potential > public.rarity_potential_cap(rarity)
            """
        )
        illegal = cur.fetchone()[0]
        log(f"illegal_academy_pot_count={illegal}")

        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE pot_visible_lo IS NOT NULL AND pot_visible_hi IS NOT NULL),
                   COUNT(*)
            FROM public.player_cards
            WHERE in_academy AND COALESCE(is_retired,false)=false
            """
        )
        with_range, total = cur.fetchone()
        log(f"academy_seats_with_ranges={with_range}/{total}")

        cur.execute(
            """
            SELECT COUNT(*) FROM public.player_cards
            WHERE in_academy AND COALESCE(is_retired,false)=false
              AND (
                SELECT COUNT(*) FROM public.player_cards pc2
                WHERE pc2.owner_id = player_cards.owner_id
                  AND pc2.in_academy AND COALESCE(pc2.is_retired,false)=false
              ) > public.academy_slot_cap(
                (SELECT COALESCE(youth_academy_level,1) FROM public.players p
                 WHERE p.discord_id = player_cards.owner_id)
              )
            """
        )
        # Simpler over-capacity club count
        cur.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT pc.owner_id, COUNT(*) AS n,
                     public.academy_slot_cap(COALESCE(MAX(p.youth_academy_level),1)) AS cap
              FROM public.player_cards pc
              JOIN public.players p ON p.discord_id = pc.owner_id
              WHERE pc.in_academy AND COALESCE(pc.is_retired,false)=false
              GROUP BY pc.owner_id
              HAVING COUNT(*) > public.academy_slot_cap(COALESCE(MAX(p.youth_academy_level),1))
            ) s
            """
        )
        over_cap_clubs = cur.fetchone()[0]
        log(f"over_capacity_grandfathered_clubs={over_cap_clubs}")

        # Function body markers from 095
        checks = {
            "process_youth_intake": ["capacity_blocked", "academy_init_visible_range", "weekly_intake"],
            "promote_academy_player": ["academy_weekly_promote_cap", "days_developed", "apply_club_economy"],
            "process_daily_academy_growth": ["age_out_grace", "finalize_due_academy_assessments", "academy_age_out_pending"],
            "sign_youth_scout_prospect": ["paid_signings_used", "paid_scout"],
            "dispatch_academy_assessment": ["academy_assess", "apply_club_economy"],
            "academy_slot_cap": ["THEN 3"],
        }
        log("--- RPC body markers ---")
        for fn, needles in checks.items():
            cur.execute(
                """
                SELECT pg_get_functiondef(p.oid)
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname='public' AND p.proname=%s
                ORDER BY p.oid DESC
                LIMIT 1
                """,
                (fn,),
            )
            row = cur.fetchone()
            if not row:
                log(f"  {fn}: MISSING")
                continue
            body = row[0]
            missing = [n for n in needles if n not in body]
            log(f"  {fn}: ok_markers={not missing} missing={missing}")

        # verify_required_schema
        verify = (ROOT / "supabase" / "scripts" / "verify_required_schema.sql").read_text(encoding="utf-8")
        cur.execute(verify)
        log("verify_required_schema.sql: PASS")

out.write_text("\n".join(lines) + "\n", encoding="utf-8")
log(f"wrote {out}")
