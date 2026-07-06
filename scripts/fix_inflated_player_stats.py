#!/usr/bin/env python3
"""Backfill: rebalance legacy god-player stats to match stored OVR / POT.

Detects cards whose uncapped weighted OVR exceeds their POT-capped OVR (hidden
stat inflation from pre-024 training). Re-rolls position-weighted stats centered
on the card's current ``overall`` so match power matches the displayed rating.

Usage:
  python scripts/fix_inflated_player_stats.py              # dry-run report
  python scripts/fix_inflated_player_stats.py --apply      # write fixes
  python scripts/fix_inflated_player_stats.py --apply --card-id <uuid>
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

from player_engine import (
    calculate_true_ovr,
    detect_stat_inflation,
    rebalance_stats_to_ovr,
    stats_from_card,
)

_DEBUG_LOG = "debug-4aa967.log"
_SESSION = "4aa967"


def _debug_log(message: str, data: dict, hypothesis_id: str = "F", run_id: str = "backfill") -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": _SESSION,
                        "runId": run_id,
                        "hypothesisId": hypothesis_id,
                        "timestamp": int(time.time() * 1000),
                        "location": "fix_inflated_player_stats.py",
                        "message": message,
                        "data": data,
                    }
                )
                + "\n"
            )
    except OSError:
        pass
    # #endregion


def _playstyles_map(db) -> dict[str, list[str]]:
    ps_res = db.table("player_playstyles").select("card_id, playstyle_key").execute()
    out: dict[str, list[str]] = {}
    for row in ps_res.data or []:
        out.setdefault(str(row["card_id"]), []).append(row["playstyle_key"])
    return out


def _fix_card(card: dict, playstyles: list[str], *, apply: bool, db) -> bool:
    card_id = str(card["id"])
    position = card.get("position") or "MID"
    overall = int(card.get("overall") or 50)
    potential = int(card.get("potential") or 85)
    stats = stats_from_card(card)

    inflated, info = detect_stat_inflation(position, stats, playstyles, overall, potential)
    if not inflated:
        return False

    rng = random.Random(hash(card_id) % (2**32))
    new_stats = rebalance_stats_to_ovr(position, overall, playstyles, potential, rng=rng)
    new_ovr = calculate_true_ovr(position, new_stats, playstyles, potential)

    after_inflated, after_info = detect_stat_inflation(
        position, new_stats, playstyles, new_ovr, potential
    )

    row = {
        "card_id": card_id,
        "name": card.get("name"),
        "position": position,
        "overall": overall,
        "potential": potential,
        "before": {**stats, **info},
        "after_stats": new_stats,
        "after_ovr": new_ovr,
        "after_hidden": after_info.get("hidden_power"),
        "still_inflated": after_inflated,
    }
    _debug_log("card rebalance plan", row)

    print(
        f"  {card.get('name')} ({position} {overall} OVR / {potential} POT): "
        f"hidden={info['hidden_power']} max_stat={info['max_stat']} "
        f"-> rebalance (new max={max(new_stats.values())}, OVR={new_ovr})"
    )

    if apply:
        db.table("player_cards").update(
            {
                "pac": new_stats["pac"],
                "sho": new_stats["sho"],
                "pas": new_stats["pas"],
                "dri": new_stats["dri"],
                "def": new_stats["def"],
                "phy": new_stats["phy"],
                "overall": new_ovr,
            }
        ).eq("id", card_id).execute()

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebalance inflated legacy player stats.")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--card-id", help="Fix a single card UUID only")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY", file=sys.stderr)
        return 1

    from supabase import create_client

    db = create_client(url, key)
    ps_map = _playstyles_map(db)

    q = db.table("player_cards").select("*")
    if args.card_id:
        q = q.eq("id", args.card_id)
    cards = (q.execute().data) or []

    if not cards:
        print("No player cards found.")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Scanning {len(cards)} card(s) for hidden stat inflation...")
    _debug_log("scan start", {"mode": mode, "card_count": len(cards)})

    fixed = 0
    for card in cards:
        if _fix_card(card, ps_map.get(str(card["id"]), []), apply=args.apply, db=db):
            fixed += 1

    _debug_log("scan complete", {"fixed": fixed, "total": len(cards)})
    print(f"{'Updated' if args.apply else 'Would fix'} {fixed}/{len(cards)} card(s).")
    if not args.apply and fixed:
        print("Re-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
