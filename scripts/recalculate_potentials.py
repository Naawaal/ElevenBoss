#!/usr/bin/env python3
"""One-time backfill: recalculate potential/base_potential for all player_cards."""
from __future__ import annotations

import os
import sys

from player_engine import generate_potential

# ponytail: requires SUPABASE_URL + SUPABASE_SERVICE_KEY in env; run manually post-migration


def main() -> int:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY", file=sys.stderr)
        return 1

    from supabase import create_client

    db = create_client(url, key)
    res = db.table("player_cards").select("id,name,overall,age,rarity,position,potential,base_potential").execute()
    cards = res.data or []
    updated = 0

    for card in cards:
        pot = generate_potential(
            card["overall"],
            card.get("age") or 25,
            card.get("rarity") or "Common",
            card.get("position") or "MID",
            rng=__import__("random").Random(hash(card["id"]) % (2**32)),
        )
        if pot == card.get("potential") and pot == card.get("base_potential"):
            continue
        db.table("player_cards").update({
            "potential": pot,
            "base_potential": pot,
        }).eq("id", card["id"]).execute()
        updated += 1
        print(f"  {card['name']}: {card.get('potential')} -> {pot}")

    print(f"Updated {updated}/{len(cards)} cards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
