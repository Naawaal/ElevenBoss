#!/usr/bin/env python3
"""
Read-only rarity potential cap inventory + dry-run reimbursement report (049 / US-42).

MANUAL_REVIEW checklist (must resolve before scripts/potential_cap_repair.py --apply):
  1. unclassified affected cards == 0
  2. every material MANUAL_REVIEW row has an explicit human compensation policy
  3. Category A rows must show refund_confidence=NONE
  4. do not invent fusion/item or marketplace damages refunds

Default: --dry-run (no card/balance writes). Optional --write-audit-dry-run inserts
repair_status=dry_run rows only.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from player_engine import RARITY_POT_CAPS, rarity_potential_cap

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

ANOMALY_SQL = """
SELECT id, owner_id, name, position, rarity, overall, potential, base_potential,
       pac, sho, pas, dri, "def", phy, skill_points, skill_points_spent, level
FROM public.player_cards
WHERE public.rarity_potential_cap(rarity) IS NULL
   OR potential > public.rarity_potential_cap(rarity)
   OR (base_potential IS NOT NULL AND base_potential > public.rarity_potential_cap(rarity))
   OR overall > potential
   OR overall > public.rarity_potential_cap(rarity)
ORDER BY rarity, overall DESC
"""


def classify(row: dict) -> tuple[str, int, int, int, str]:
    rarity = row["rarity"]
    cap = rarity_potential_cap(rarity)
    old_ovr = int(row["overall"])
    old_pot = int(row["potential"])
    old_base = int(row["base_potential"] if row["base_potential"] is not None else old_pot)
    new_pot = min(old_pot, cap)
    new_base = min(old_base, cap)
    if old_ovr <= cap and old_ovr <= new_pot:
        return "A", old_ovr, new_pot, new_base, "NONE"
    # OVR illegal — repair must reduce attrs; refunds need evidence
    new_ovr = min(old_ovr, new_pot, cap)
    confidence = "RECONSTRUCTED" if int(row.get("skill_points_spent") or 0) > 0 else "MANUAL_REVIEW"
    if old_ovr > cap and int(row.get("skill_points_spent") or 0) == 0:
        # likely generated illegal — Category C
        return "C", new_ovr, new_pot, new_base, confidence if confidence != "NONE" else "NONE"
    return "B", new_ovr, new_pot, new_base, confidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "potential_cap_dryrun.csv")
    parser.add_argument(
        "--write-audit-dry-run",
        action="store_true",
        help="Insert dry_run rows into potential_cap_repair_audit (no card mutations)",
    )
    parser.add_argument("--batch-id", default="dryrun")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1

    import psycopg
    from psycopg.rows import dict_row

    dsn = url.replace("postgresql+asyncpg://", "postgresql://")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(ANOMALY_SQL)
            rows = cur.fetchall()

        counts = Counter()
        conf = Counter()
        report_rows = []
        for row in rows:
            cat, new_ovr, new_pot, new_base, confidence = classify(row)
            counts[cat] += 1
            conf[confidence] += 1
            counts[row["rarity"]] += 1
            report_rows.append(
                {
                    **{k: row[k] for k in row},
                    "legal_cap": RARITY_POT_CAPS.get(row["rarity"]),
                    "category": cat,
                    "proposed_overall": new_ovr,
                    "proposed_potential": new_pot,
                    "proposed_base_potential": new_base,
                    "refund_confidence": confidence,
                    "proposed_refund_sp": max(0, int(row["overall"]) - new_ovr)
                    if cat in {"B", "C"} and confidence == "RECONSTRUCTED"
                    else 0,
                    "proposed_refund_coins": 0,
                    "proposed_refund_energy": 0,
                }
            )

        with args.out.open("w", newline="", encoding="utf-8") as fh:
            if report_rows:
                writer = csv.DictWriter(fh, fieldnames=list(report_rows[0].keys()))
                writer.writeheader()
                writer.writerows(report_rows)
            else:
                fh.write("no_anomalies\n")

        if args.write_audit_dry_run and report_rows:
            with conn.cursor() as cur:
                for r in report_rows:
                    cur.execute(
                        """
                        INSERT INTO public.potential_cap_repair_audit (
                            batch_id, card_id, owner_id, rarity,
                            old_overall, new_overall, old_potential, new_potential,
                            old_base_potential, new_base_potential,
                            old_stats, refund_confidence, repair_category, repair_status
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s::jsonb, %s, %s, 'dry_run'
                        )
                        ON CONFLICT (batch_id, card_id) DO NOTHING
                        """,
                        (
                            args.batch_id,
                            r["id"],
                            r["owner_id"],
                            r["rarity"],
                            r["overall"],
                            r["proposed_overall"],
                            r["potential"],
                            r["proposed_potential"],
                            r["base_potential"],
                            r["proposed_base_potential"],
                            json.dumps(
                                {
                                    "pac": r["pac"],
                                    "sho": r["sho"],
                                    "pas": r["pas"],
                                    "dri": r["dri"],
                                    "def": r["def"],
                                    "phy": r["phy"],
                                }
                            ),
                            r["refund_confidence"],
                            r["category"],
                        ),
                    )
            conn.commit()

    print(f"anomalies={len(rows)} categories={dict(counts)} confidence={dict(conf)}")
    print(f"wrote {args.out}")
    print("No card/balance mutations performed." if args.dry_run else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
