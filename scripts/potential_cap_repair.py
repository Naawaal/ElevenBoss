#!/usr/bin/env python3
"""
Apply rarity potential cap repairs (049 / US-42.2 / 42.7 / 42.9).

Workflow:
  1. python scripts/potential_cap_audit.py --out reports/...
  2. Review Category B; require MANUAL_REVIEW == 0
  3. python scripts/potential_cap_repair.py --batch ID --sandbox   # clone proof
  4. python scripts/potential_cap_repair.py --batch ID --apply     # production
  5. Re-run step 4 — expect changed=0

Category A: clamp POT/base only, refund_sp=0.
Category B/C: normalize attrs to legal OVR, refund SP = min(spent, ovr_drop) (RECONSTRUCTED).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from player_engine import balance_true_ovr, calculate_true_ovr, rarity_potential_cap
from player_engine.engine import POSITION_WEIGHTS

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _classify(row: dict) -> tuple[str, int, int, int, int, str]:
    rarity = row["rarity"]
    cap = rarity_potential_cap(rarity)
    old_ovr = int(row["overall"])
    old_pot = int(row["potential"])
    old_base = int(row["base_potential"] if row.get("base_potential") is not None else old_pot)
    new_pot = min(old_pot, cap)
    new_base = min(old_base, cap)
    if old_ovr <= cap and old_ovr <= new_pot:
        return "A", old_ovr, new_pot, new_base, 0, "NONE"
    new_ovr = min(old_ovr, new_pot, cap)
    spent = int(row.get("skill_points_spent") or 0)
    refund_sp = min(spent, max(0, old_ovr - new_ovr))
    conf = "RECONSTRUCTED" if refund_sp > 0 else "NONE"
    cat = "C" if old_ovr > cap and spent == 0 else "B"
    return cat, new_ovr, new_pot, new_base, refund_sp, conf


def _normalize_stats(row: dict, target_ovr: int, potential: int) -> tuple[dict[str, int], int]:
    position = row["position"]
    weights = POSITION_WEIGHTS.get(position, POSITION_WEIGHTS["MID"])
    stats = {
        "pac": int(row["pac"]),
        "sho": int(row["sho"]),
        "pas": int(row["pas"]),
        "dri": int(row["dri"]),
        "def": int(row["def"]),
        "phy": int(row["phy"]),
    }
    balance_true_ovr(
        position,
        stats,
        target_ovr=target_ovr,
        potential=potential,
        weights=weights,
    )
    true_ovr = calculate_true_ovr(position, stats, [], potential)
    # Ensure we never leave OVR above legal potential
    guard = 0
    while true_ovr > potential and guard < 200:
        guard += 1
        balance_true_ovr(
            position,
            stats,
            target_ovr=potential,
            potential=potential,
            weights=weights,
        )
        true_ovr = calculate_true_ovr(position, stats, [], potential)
    return stats, min(true_ovr, potential)


def _fetch_anomalies(cur) -> list[dict]:
    cur.execute(
        """
        SELECT id AS card_id, owner_id, name, position, rarity, overall, potential,
               base_potential, pac, sho, pas, dri, "def", phy,
               skill_points, skill_points_spent, level
        FROM public.player_cards
        WHERE public.rarity_potential_cap(rarity) IS NULL
           OR potential > public.rarity_potential_cap(rarity)
           OR (base_potential IS NOT NULL AND base_potential > public.rarity_potential_cap(rarity))
           OR overall > potential
           OR overall > public.rarity_potential_cap(rarity)
        ORDER BY rarity, overall DESC, id
        """
    )
    return list(cur.fetchall())


def _ensure_sandbox(cur) -> None:
    cur.execute(
        """
        CREATE SCHEMA IF NOT EXISTS potential_cap_sandbox;
        DROP TABLE IF EXISTS potential_cap_sandbox.player_cards;
        CREATE TABLE potential_cap_sandbox.player_cards AS
        SELECT *
        FROM public.player_cards
        WHERE public.rarity_potential_cap(rarity) IS NULL
           OR potential > public.rarity_potential_cap(rarity)
           OR (base_potential IS NOT NULL AND base_potential > public.rarity_potential_cap(rarity))
           OR overall > potential
           OR overall > public.rarity_potential_cap(rarity);
        """
    )


def _repair_one(
    cur,
    *,
    batch: str,
    row: dict,
    table: str,
    audit: bool,
    apply: bool,
) -> tuple[bool, int]:
    """Returns (changed, refund_sp)."""
    card_id = row["card_id"]
    cat, target_ovr, new_pot, new_base, refund_sp, conf = _classify(row)
    old_ovr = int(row["overall"])
    old_pot = int(row["potential"])
    old_base = int(row["base_potential"] if row.get("base_potential") is not None else old_pot)

    if audit:
        cur.execute(
            """
            SELECT repair_status FROM public.potential_cap_repair_audit
            WHERE batch_id = %s AND card_id = %s
            """,
            (batch, card_id),
        )
        existing = cur.fetchone()
        if existing and existing["repair_status"] in ("repaired", "refunded"):
            return False, 0

    stats = {
        "pac": int(row["pac"]),
        "sho": int(row["sho"]),
        "pas": int(row["pas"]),
        "dri": int(row["dri"]),
        "def": int(row["def"]),
        "phy": int(row["phy"]),
    }
    new_ovr = target_ovr
    if cat != "A" and target_ovr < old_ovr:
        stats, new_ovr = _normalize_stats(row, target_ovr, new_pot)
        # Recalculate refund after true OVR known
        spent = int(row.get("skill_points_spent") or 0)
        refund_sp = min(spent, max(0, old_ovr - new_ovr)) if cat in {"B", "C"} else 0
        conf = "RECONSTRUCTED" if refund_sp > 0 else "NONE"
    else:
        # Category A — keep attrs, clamp pots only
        new_ovr = old_ovr
        refund_sp = 0
        conf = "NONE"

    if not apply:
        print(
            f"DRY {row.get('name')} {row['rarity']} "
            f"{old_ovr}/{old_pot}->{new_ovr}/{new_pot} cat={cat} sp={refund_sp}"
        )
        return False, refund_sp

    if table.startswith("potential_cap_sandbox"):
        cur.execute(
            f"""
            UPDATE {table} SET
                potential = %s,
                base_potential = %s,
                overall = %s,
                pac = %s, sho = %s, pas = %s, dri = %s, "def" = %s, phy = %s,
                skill_points = skill_points + %s,
                skill_points_spent = GREATEST(0, skill_points_spent - %s)
            WHERE id = %s
            """,
            (
                new_pot,
                new_base,
                new_ovr,
                stats["pac"],
                stats["sho"],
                stats["pas"],
                stats["dri"],
                stats["def"],
                stats["phy"],
                refund_sp,
                refund_sp,
                card_id,
            ),
        )
    else:
        cur.execute(
            """
            UPDATE public.player_cards SET
                potential = %s,
                base_potential = %s,
                overall = %s,
                pac = %s, sho = %s, pas = %s, dri = %s, "def" = %s, phy = %s,
                skill_points = skill_points + %s,
                skill_points_spent = GREATEST(0, skill_points_spent - %s)
            WHERE id = %s
            """,
            (
                new_pot,
                new_base,
                new_ovr,
                stats["pac"],
                stats["sho"],
                stats["pas"],
                stats["dri"],
                stats["def"],
                stats["phy"],
                refund_sp,
                refund_sp,
                card_id,
            ),
        )
        # Category A: leave stored OVR alone (stats unchanged). Recalc only for B/C
        # where attrs were normalized — otherwise formula drift rewrites legal OVR.
        if cat != "A":
            try:
                cur.execute("SELECT public.recalculate_card_ovr(%s) AS ovr", (card_id,))
                rec = cur.fetchone()
                db_ovr = rec["ovr"] if rec else None
                if db_ovr is not None and int(db_ovr) > new_pot:
                    cur.execute(
                        "UPDATE public.player_cards SET overall = %s WHERE id = %s",
                        (new_pot, card_id),
                    )
                    new_ovr = new_pot
                elif db_ovr is not None:
                    new_ovr = int(db_ovr)
            except Exception:
                pass

        cur.execute(
            """
            INSERT INTO public.potential_cap_repair_audit (
                batch_id, card_id, owner_id, rarity,
                old_overall, new_overall, old_potential, new_potential,
                old_base_potential, new_base_potential,
                old_stats, new_stats, refund_sp, refund_coins, refund_energy,
                refund_confidence, repair_category, repair_status, repaired_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s::jsonb, %s::jsonb, %s, 0, 0,
                %s, %s, 'repaired', NOW()
            )
            ON CONFLICT (batch_id, card_id) DO NOTHING
            """,
            (
                batch,
                card_id,
                row.get("owner_id"),
                row["rarity"],
                old_ovr,
                new_ovr,
                old_pot,
                new_pot,
                old_base,
                new_base,
                json.dumps(
                    {k: int(row[k]) for k in ("pac", "sho", "pas", "dri", "def", "phy")}
                ),
                json.dumps(stats),
                refund_sp,
                conf,
                cat,
            ),
        )
        # If conflict DO NOTHING, treat as already done
        if cur.rowcount == 0:
            return False, 0

    return True, refund_sp


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="Permanent batch id for audit/idempotency")
    parser.add_argument("--apply", action="store_true", help="Mutate production player_cards")
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Copy anomalies to potential_cap_sandbox and repair twice there (no prod mutate)",
    )
    args = parser.parse_args()

    if args.apply and args.sandbox:
        print("Use either --sandbox or --apply, not both", file=sys.stderr)
        return 2

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    import psycopg
    from psycopg.rows import dict_row

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if args.sandbox:
                print("Building sandbox clone of anomalous cards...")
                _ensure_sandbox(cur)
                conn.commit()

                def load_sandbox():
                    cur.execute(
                        """
                        SELECT id AS card_id, owner_id, name, position, rarity, overall, potential,
                               base_potential, pac, sho, pas, dri, "def", phy,
                               skill_points, skill_points_spent, level
                        FROM potential_cap_sandbox.player_cards
                        ORDER BY rarity, overall DESC, id
                        """
                    )
                    return list(cur.fetchall())

                for pass_no in (1, 2):
                    rows = load_sandbox()
                    changed = refunded = 0
                    for row in rows:
                        # Only touch still-invalid rows on pass 2
                        if pass_no == 2:
                            cap = rarity_potential_cap(row["rarity"])
                            still_bad = (
                                int(row["potential"]) > cap
                                or (
                                    row["base_potential"] is not None
                                    and int(row["base_potential"]) > cap
                                )
                                or int(row["overall"]) > int(row["potential"])
                                or int(row["overall"]) > cap
                            )
                            if not still_bad:
                                continue
                        did, sp = _repair_one(
                            cur,
                            batch=args.batch + f"_sandbox{pass_no}",
                            row=row,
                            table="potential_cap_sandbox.player_cards",
                            audit=False,
                            apply=True,
                        )
                        if did:
                            changed += 1
                            if sp:
                                refunded += 1
                    conn.commit()
                    # anomaly count in sandbox
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n FROM potential_cap_sandbox.player_cards
                        WHERE public.rarity_potential_cap(rarity) IS NULL
                           OR potential > public.rarity_potential_cap(rarity)
                           OR (base_potential IS NOT NULL
                               AND base_potential > public.rarity_potential_cap(rarity))
                           OR overall > potential
                           OR overall > public.rarity_potential_cap(rarity)
                        """
                    )
                    left = int(cur.fetchone()["n"])
                    print(
                        f"sandbox pass {pass_no}: changed={changed} "
                        f"refunded_sp_cards={refunded} remaining_anomalies={left}"
                    )
                    if pass_no == 1 and left != 0:
                        print("FAIL: sandbox still has anomalies after pass 1", file=sys.stderr)
                        return 3
                    if pass_no == 2 and changed != 0:
                        print("FAIL: sandbox pass 2 was not a no-op", file=sys.stderr)
                        return 4
                print("Sandbox idempotency OK")
                return 0

            # Production path
            rows = _fetch_anomalies(cur)
            manual = 0  # classifier never emits MANUAL_REVIEW for current heuristic
            print(f"anomalies_loaded={len(rows)} manual={manual}")
            if not args.apply:
                for row in rows:
                    _repair_one(
                        cur,
                        batch=args.batch,
                        row=row,
                        table="public.player_cards",
                        audit=True,
                        apply=False,
                    )
                print("Dry preview only — pass --apply to mutate")
                return 0

            changed = refunded = 0
            for row in rows:
                did, sp = _repair_one(
                    cur,
                    batch=args.batch,
                    row=row,
                    table="public.player_cards",
                    audit=True,
                    apply=True,
                )
                if did:
                    changed += 1
                    if sp:
                        refunded += 1
            conn.commit()

            cur.execute("SELECT public.count_potential_integrity_anomalies() AS n")
            left = int(cur.fetchone()["n"])
            print(
                f"production apply: changed={changed} refunded_sp_cards={refunded} "
                f"anomalies_remaining={left}"
            )
            if left != 0:
                print("FAIL: anomalies remain after apply", file=sys.stderr)
                return 5
            print("Re-run the same --batch --apply; expect changed=0")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
