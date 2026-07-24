"""Ad-hoc: best formation + XI by band OVR for a club."""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from match_engine.formation_positions import FORMATION_COORDINATES, _role_from_label

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
CLUB = int(os.environ.get("CLUB_ID", "976054227459776582"))


def band_needs(formation: str) -> dict[str, int]:
    coords = FORMATION_COORDINATES[formation]
    need: Counter[str] = Counter()
    for label in coords:
        need[_role_from_label(label, formation)] += 1
    return dict(need)


def pick_xi(elig: list[dict], need: dict[str, int]):
    used: set[str] = set()
    xi: dict[str, list] = {b: [] for b in need}
    for band, n in need.items():
        pool = sorted(
            [p for p in elig if p["pos"] == band and p["id"] not in used],
            key=lambda p: (p["ovr"], p["pot"], p["fatigue"]),
            reverse=True,
        )
        chosen = pool[:n]
        for p in chosen:
            used.add(p["id"])
        xi[band] = chosen
    filled = sum(len(v) for v in xi.values())
    total = sum(p["ovr"] for v in xi.values() for p in v)
    avg = total / max(filled, 1)
    missing = {b: need[b] - len(xi[b]) for b in need if len(xi[b]) < need[b]}
    return xi, filled, avg, total, missing


def main() -> None:
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select manager_name, club_name, coins from players where discord_id=%s",
                (CLUB,),
            )
            club = cur.fetchone()
            cur.execute(
                """
                select id::text, name, position, rarity, overall, potential,
                       coalesce(fatigue,100) as fatigue,
                       coalesce(in_hospital,false), injury_tier,
                       coalesce(is_retired,false), coalesce(in_academy,false)
                from player_cards where owner_id=%s
                order by overall desc, potential desc
                """,
                (CLUB,),
            )
            rows = cur.fetchall()
            cur.execute("select formation from squads where discord_id=%s", (CLUB,))
            sq = cur.fetchone()

    print("CLUB", club)
    print("CURRENT_FORMATION", sq[0] if sq else None)

    elig = []
    for r in rows:
        if r[9] or r[10]:
            continue
        if r[7] or r[8]:
            continue
        elig.append(
            {
                "id": r[0],
                "name": r[1],
                "pos": r[2],
                "rarity": r[3],
                "ovr": r[4],
                "pot": r[5],
                "fatigue": r[6],
            }
        )

    print("ELIGIBLE", len(elig), "TOTAL", len(rows))
    print("BY POS", dict(Counter(p["pos"] for p in elig)))
    print("TOP BY POS:")
    for pos in ["GK", "DEF", "MID", "FWD"]:
        pool = sorted(
            [p for p in elig if p["pos"] == pos],
            key=lambda p: (p["ovr"], p["pot"]),
            reverse=True,
        )
        print(pos, [(p["name"], p["ovr"], p["pot"], p["rarity"]) for p in pool[:6]])

    print("\n=== FORMATION SCORES ===")
    best = None
    for name in FORMATION_COORDINATES:
        need = band_needs(name)
        xi, filled, avg, total, missing = pick_xi(elig, need)
        print(
            f"{name}: bands={need} filled={filled}/11 "
            f"avg_ovr={avg:.2f} total={total} missing={missing or None}"
        )
        score = (filled == 11, avg, total)
        if best is None or score > best[0]:
            best = (score, name, xi, avg, total, missing, need)

    assert best is not None
    _, rec, xi, avg, total, missing, need = best
    print(f"\nRECOMMENDED {rec}  avg_ovr={avg:.2f}  XI_total_OVR={total}")
    print(f"bands needed: {need}")
    for band in ["GK", "DEF", "MID", "FWD"]:
        for p in xi.get(band, []):
            print(
                f"  {band:3} | {p['name']:22} | {p['rarity']:10} | "
                f"OVR {p['ovr']:2} | POT {p['pot']:2} | fit {p['fatigue']}"
            )


if __name__ == "__main__":
    main()
