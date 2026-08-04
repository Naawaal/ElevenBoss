"""Feature 052 Phase 3 — YA V2 E2E acceptance on isolated test club 900000000000000052."""
from __future__ import annotations

import os
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))

from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Jsonb

from apps.discord_bot.core.card_payload import card_rpc_payload
from economy.facility_effects import youth_facility_preview
from gacha.generator import _load_names
from player_engine import init_visible_range, narrow_range, rarity_potential_cap
from player_engine.youth_intake import generate_youth_intake_cards

load_dotenv(ROOT / ".env")
TEST_OWNER = 900000000000000052
OUT = ROOT / "specs" / "052-youth-academy-v2-acceptance" / "evidence" / "e2e-acceptance.txt"

lines: list[str] = []
failures: list[str] = []


def log(msg: str) -> None:
    print(msg)
    lines.append(msg)


def fail(msg: str) -> None:
    failures.append(msg)
    log(f"FAIL: {msg}")


def ok(msg: str) -> None:
    log(f"PASS: {msg}")


def gen(n: int, level: int, seed: int, *, legendary_enabled: bool = True):
    names = _load_names()
    return generate_youth_intake_cards(
        n,
        academy_level=level,
        first_names=names["first"],
        last_names=names["last"],
        rng=random.Random(seed),
        legendary_enabled=legendary_enabled,
    )


def ensure_test_club(cur) -> None:
    cur.execute("SELECT 1 FROM public.players WHERE discord_id = %s", (TEST_OWNER,))
    if cur.fetchone():
        return
    cur.execute(
        """
        INSERT INTO public.players (
          discord_id, username, club_name, coins, action_energy, max_energy,
          youth_academy_level, training_ground_level, is_ai
        ) VALUES (
          %s, 'ya_v2_acceptance_052', '052 YA Acceptance FC', 100000, 100, 120, 1, 1, FALSE
        )
        """,
        (TEST_OWNER,),
    )


def wipe_academy(cur) -> None:
    cur.execute("DELETE FROM public.academy_scout_assessments WHERE owner_id = %s", (TEST_OWNER,))
    cur.execute("DELETE FROM public.player_cards WHERE owner_id = %s", (TEST_OWNER,))
    cur.execute("DELETE FROM public.youth_intake_log WHERE owner_id = %s", (TEST_OWNER,))
    cur.execute("DELETE FROM public.academy_weekly_actions WHERE owner_id = %s", (TEST_OWNER,))
    cur.execute("DELETE FROM public.scouting_reports WHERE owner_id = %s", (TEST_OWNER,))
    cur.execute(
        "DELETE FROM public.economy_ledger WHERE club_id = %s AND source LIKE 'academy%%'",
        (TEST_OWNER,),
    )


def set_ya_level(cur, level: int) -> None:
    cur.execute(
        "UPDATE public.players SET youth_academy_level = %s, coins = 100000 WHERE discord_id = %s",
        (level, TEST_OWNER),
    )


def seat_n(cur, n: int, *, level: int = 1, seed: int = 52) -> list[uuid.UUID]:
    cards = gen(n, level, seed)
    ids: list[uuid.UUID] = []
    for c in cards:
        p = card_rpc_payload(c)
        lo, hi = init_visible_range(int(p["potential"]), str(p["rarity"]), level)
        cur.execute(
            """
            INSERT INTO public.player_cards (
              owner_id, name, position, rarity, base_rating, level, overall,
              pac, sho, pas, dri, "def", phy, potential, base_potential, age, date_of_birth, role,
              in_academy, academy_progress, academy_seated_at,
              pot_visible_lo, pot_visible_hi, scout_assessment_level, academy_origin
            ) VALUES (
              %s, %s, %s, %s, %s, 1, %s,
              %s, %s, %s, %s, %s, %s, %s, %s, %s,
              (CURRENT_DATE - (%s || ' years')::interval)::date,
              %s,
              TRUE, 0, NOW(), %s, %s, 'none', 'admin'
            ) RETURNING id
            """,
            (
                TEST_OWNER,
                p["name"],
                p["position"],
                p["rarity"],
                p["overall"],
                p["overall"],
                p["pac"],
                p["sho"],
                p["pas"],
                p["dri"],
                p["def"],
                p["phy"],
                p["potential"],
                p["base_potential"],
                p["age"],
                str(p["age"]),
                p["role"],
                lo,
                hi,
            ),
        )
        ids.append(cur.fetchone()[0])
    return ids


def main() -> int:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    log(f"TEST_OWNER={TEST_OWNER}")
    log(f"started={datetime.now(timezone.utc).isoformat()}")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            ensure_test_club(cur)
            wipe_academy(cur)
            set_ya_level(cur, 1)
            conn.commit()

            # Rarity ceilings
            for level in range(1, 6):
                for c in gen(8, level, level * 17):
                    if c.potential > rarity_potential_cap(c.rarity):
                        fail(f"L{level} {c.rarity} POT {c.potential} > cap")
                    if c.overall > c.potential:
                        fail(f"L{level} OVR>POT")
                    if level < 5 and c.rarity == "Legendary":
                        fail(f"Legendary at L{level}")
            kill = gen(40, 5, 3, legendary_enabled=False)
            if any(c.rarity == "Legendary" for c in kill):
                fail("Legendary with kill switch")
            else:
                ok("ceilings + no Legendary below L5 + kill switch")

            # Empty L1 intake
            wipe_academy(cur)
            set_ya_level(cur, 1)
            conn.commit()
            payload = [card_rpc_payload(c) for c in gen(2, 1, 99)]
            cur.execute("SELECT public.process_youth_intake(%s, %s)", (TEST_OWNER, Jsonb(payload)))
            res = cur.fetchone()[0]
            conn.commit()
            if int(res.get("seated", 0)) != 2:
                fail(f"empty L1 seated!=2 {res}")
            else:
                ok("empty L1 intake seated=2")

            cur.execute("SELECT public.process_youth_intake(%s, %s)", (TEST_OWNER, Jsonb(payload)))
            res2 = cur.fetchone()[0]
            conn.commit()
            if not res2.get("already_processed"):
                fail(f"not idempotent {res2}")
            else:
                ok("same-week intake idempotent")

            # Partial
            wipe_academy(cur)
            seat_n(cur, 2, level=1, seed=21)
            cur.execute("DELETE FROM public.youth_intake_log WHERE owner_id=%s", (TEST_OWNER,))
            conn.commit()
            payload = [card_rpc_payload(c) for c in gen(2, 1, 22)]
            cur.execute("SELECT public.process_youth_intake(%s, %s)", (TEST_OWNER, Jsonb(payload)))
            res = cur.fetchone()[0]
            conn.commit()
            if int(res.get("seated", -1)) != 1 or int(res.get("skipped", -1)) != 1:
                fail(f"partial {res}")
            else:
                ok("partial seats only free slot")

            # Full
            wipe_academy(cur)
            seat_n(cur, 3, level=1, seed=23)
            cur.execute("DELETE FROM public.youth_intake_log WHERE owner_id=%s", (TEST_OWNER,))
            conn.commit()
            payload = [card_rpc_payload(c) for c in gen(2, 1, 24)]
            cur.execute("SELECT public.process_youth_intake(%s, %s)", (TEST_OWNER, Jsonb(payload)))
            res = cur.fetchone()[0]
            conn.commit()
            if int(res.get("seated", -1)) != 0 or not res.get("capacity_blocked"):
                fail(f"full {res}")
            else:
                ok("full academy capacity_blocked")

            # Over-cap
            wipe_academy(cur)
            seat_n(cur, 3, level=1, seed=25)
            seat_n(cur, 1, level=1, seed=26)
            cur.execute(
                "SELECT COUNT(*) FROM public.player_cards WHERE owner_id=%s AND in_academy",
                (TEST_OWNER,),
            )
            n = cur.fetchone()[0]
            cur.execute("DELETE FROM public.youth_intake_log WHERE owner_id=%s", (TEST_OWNER,))
            conn.commit()
            payload = [card_rpc_payload(c) for c in gen(2, 1, 27)]
            cur.execute("SELECT public.process_youth_intake(%s, %s)", (TEST_OWNER, Jsonb(payload)))
            res = cur.fetchone()[0]
            conn.commit()
            if n < 4 or int(res.get("seated", -1)) != 0:
                fail(f"over-cap n={n} res={res}")
            else:
                ok(f"over-capacity blocks intake (occupied={n})")

            # Scout range ladder
            pot, rarity = 78, "Rare"
            lo, hi = init_visible_range(pot, rarity, 2)
            for tier in ("quick", "standard", "deep"):
                nlo, nhi = narrow_range(lo, hi, pot, tier, rarity=rarity)
                if nlo < lo or nhi > hi or not (nlo <= pot <= nhi):
                    fail(f"narrow {tier}")
                lo, hi = nlo, nhi
            ok(f"scout ladder ends {lo}-{hi}")

            # Assess RPC
            wipe_academy(cur)
            cid = seat_n(cur, 1, level=1, seed=30)[0]
            conn.commit()
            cur.execute(
                "SELECT public.dispatch_academy_assessment(%s, %s, 'quick')",
                (TEST_OWNER, cid),
            )
            cur.fetchone()
            conn.commit()
            try:
                cur.execute(
                    "SELECT public.dispatch_academy_assessment(%s, %s, 'standard')",
                    (TEST_OWNER, cid),
                )
                cur.fetchone()
                conn.commit()
                fail("double assess allowed")
            except Exception as exc:
                conn.rollback()
                if "already in progress" in str(exc).lower():
                    ok("double assess rejected")
                else:
                    fail(f"double assess: {exc}")

            cur.execute(
                """
                UPDATE public.academy_scout_assessments
                SET finishes_at = NOW() - interval '1 minute'
                WHERE card_id = %s AND status = 'pending'
                """,
                (cid,),
            )
            cur.execute(
                "SELECT potential, rarity, pot_visible_lo, pot_visible_hi, pac, overall "
                "FROM public.player_cards WHERE id=%s",
                (cid,),
            )
            before = cur.fetchone()
            cur.execute(
                "SELECT public.finalize_academy_assessment(%s, %s)",
                (TEST_OWNER, cid),
            )
            cur.fetchone()
            cur.execute(
                "SELECT potential, rarity, pot_visible_lo, pot_visible_hi, pac, overall "
                "FROM public.player_cards WHERE id=%s",
                (cid,),
            )
            after = cur.fetchone()
            conn.commit()
            if before[0] != after[0] or before[1] != after[1] or before[4] != after[4]:
                fail(f"identity mutated {before} -> {after}")
            elif after[2] < before[2] or after[3] > before[3]:
                fail(f"range widened {before[2:4]} -> {after[2:4]}")
            elif not (after[2] <= before[0] <= after[3]):
                fail("lost true POT")
            else:
                ok(f"assess ok range {after[2]}-{after[3]}")

            # Promote weekly cap
            wipe_academy(cur)
            ids = seat_n(cur, 3, level=1, seed=40)
            conn.commit()
            for i, pid in enumerate(ids[:2]):
                cur.execute(
                    "SELECT public.promote_academy_player(%s, %s)",
                    (TEST_OWNER, pid),
                )
                pr = cur.fetchone()[0]
                conn.commit()
                if int(pr.get("promotes_used", 0)) != i + 1:
                    fail(f"promote counter {pr}")
                else:
                    ok(f"promote #{i+1} fee={pr.get('fee')} name={pr.get('name')}")
            try:
                cur.execute(
                    "SELECT public.promote_academy_player(%s, %s)",
                    (TEST_OWNER, ids[2]),
                )
                cur.fetchone()
                conn.commit()
                fail("third promote allowed")
            except Exception as exc:
                conn.rollback()
                if "limit" in str(exc).lower():
                    ok("third promote blocked")
                else:
                    fail(f"third promote: {exc}")

            cur.execute(
                "SELECT id FROM public.player_cards WHERE owner_id=%s AND in_academy LIMIT 1",
                (TEST_OWNER,),
            )
            rem = cur.fetchone()
            if rem:
                rid = rem[0]
                cur.execute(
                    "SELECT public.release_academy_player(%s, %s)",
                    (TEST_OWNER, rid),
                )
                cur.fetchone()
                conn.commit()
                try:
                    cur.execute(
                        "SELECT public.promote_academy_player(%s, %s)",
                        (TEST_OWNER, rid),
                    )
                    cur.fetchone()
                    conn.commit()
                    fail("promote after release")
                except Exception:
                    conn.rollback()
                    ok("released cannot promote")

            prev = youth_facility_preview(1)
            if prev and prev["capacity"] == (3, 3) and prev["range_width"][1] <= prev["range_width"][0]:
                ok(f"facility preview {prev['capacity']} {prev['range_width']}")
            else:
                fail(f"facility preview {prev}")

            # Aging decay pure
            from player_engine.youth_math import apply_academy_aging_decay, should_age_warn

            if not should_age_warn(20):
                fail("age warn")
            if apply_academy_aging_decay(80, 78, 85) != 79:
                fail("decay")
            if apply_academy_aging_decay(78, 78, 85) != 78:
                fail("decay floor ovr")
            ok("aging warn/decay bounds")

            # Age-out pending + grace release via growth job path
            wipe_academy(cur)
            cid = seat_n(cur, 1, level=1, seed=50)[0]
            cur.execute(
                """
                UPDATE public.player_cards
                SET date_of_birth = (CURRENT_DATE - interval '22 years')::date,
                    age = 22,
                    academy_age_out_pending_at = NOW() - interval '100 hours',
                    academy_warned_aging_at = NOW() - interval '200 hours'
                WHERE id = %s
                """,
                (cid,),
            )
            conn.commit()
            cur.execute("SELECT public.process_daily_academy_growth()")
            growth = cur.fetchone()[0]
            conn.commit()
            cur.execute(
                "SELECT 1 FROM public.player_cards WHERE id=%s",
                (cid,),
            )
            still = cur.fetchone()
            released = growth.get("age_out_released") or []
            if still is not None:
                fail(f"age-out grace should auto-release; growth={growth}")
            else:
                ok(f"age-out grace auto-release released_n={len(released)}")

            wipe_academy(cur)
            conn.commit()

    log(f"finished failures={len(failures)}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if failures:
        for f in failures:
            log(f"  - {f}")
        return 1
    log("ALL_E2E_CHECKS_PASSED")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
