"""Roster snapshot for a club (scratch)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
CLUB = 840864839240253440

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT manager_name, club_name, coins
            FROM public.players
            WHERE discord_id = %s
            """,
            (CLUB,),
        )
        club = cur.fetchone()
        print("CLUB:", club)

        cur.execute(
            """
            SELECT id, name, position, rarity, overall, potential,
                   pac, sho, pas, dri, "def", phy
            FROM public.player_cards
            WHERE owner_id = %s
              AND COALESCE(is_retired, false) = false
            ORDER BY overall DESC, potential DESC
            """,
            (CLUB,),
        )
        rows = cur.fetchall()
        print(f"ROSTER_COUNT: {len(rows)}")

        if not rows:
            raise SystemExit("No cards")

        # Highest OVR
        by_ovr = sorted(rows, key=lambda r: (r[4], r[5]), reverse=True)
        # Highest POT
        by_pot = sorted(rows, key=lambda r: (r[5], r[4]), reverse=True)

        print("\n=== Highest OVR (top 5) ===")
        for r in by_ovr[:5]:
            print(f"  {r[1]} | {r[2]} | {r[3]} | OVR {r[4]} | POT {r[5]}")

        print("\n=== Highest POT (top 5) ===")
        for r in by_pot[:5]:
            print(f"  {r[1]} | {r[2]} | {r[3]} | OVR {r[4]} | POT {r[5]}")

        # Fair value sum using same heuristic as economy if available via SQL-less python
        from economy import fair_value_coins

        total = 0
        valued = []
        for r in rows:
            # age unknown here — fair_value can work without age
            try:
                fv = fair_value_coins(int(r[4]), str(r[3] or "Common"), potential=int(r[5] or 0) or None)
            except Exception:
                fv = 0
            total += fv
            valued.append((fv, r))
        valued.sort(reverse=True)
        print("\n=== Highest fair value (top 5) ===")
        for fv, r in valued[:5]:
            print(f"  {r[1]} | {r[2]} | {r[3]} | OVR {r[4]} | POT {r[5]} | ~🪙 {fv:,}")

        print(f"\n=== Club total estimated fair value ===")
        print(f"  Cards: {len(rows)}")
        print(f"  Sum fair value: 🪙 {total:,}")
        if club:
            print(f"  Coins on hand: 🪙 {int(club[2] or 0):,}")
            print(f"  Club liquid+squad (approx): 🪙 {total + int(club[2] or 0):,}")
