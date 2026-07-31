"""Replay Mirai vs Crimson friendly seed + variance sample (no Supabase)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "packages" / "match_engine"),
    str(ROOT / "packages" / "player_engine"),
    str(ROOT / "packages" / "economy"),
]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

MIRAI = 976054227459776582
CRIMSON = 840864839240253440
SEED = 6119542298684486057


def load_xi(cur, owner_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT pc.id, pc.name, pc.overall, pc.position, pc.pac, pc.sho, pc.pas,
               pc.dri, pc.def, pc.phy, pc.morale, pc.fatigue
        FROM squad_assignments sa
        JOIN player_cards pc ON pc.id = sa.player_card_id
        WHERE sa.discord_id = %s
        ORDER BY sa.position_slot
        """,
        (owner_id,),
    )
    return list(cur.fetchall())


async def main() -> None:
    from apps.discord_bot.core.match_cards import card_from_db_row
    from match_engine import MatchState, collect_match_events_v3, format_zone_breakdown

    with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
        mirai_rows = load_xi(cur, MIRAI)
        crimson_rows = load_xi(cur, CRIMSON)

    mirai = [card_from_db_row(r) for r in mirai_rows]
    crimson = [card_from_db_row(r) for r in crimson_rows]

    print("match OVRs (morale-adjusted):")
    for label, squad in (("Mirai", mirai), ("Crimson", crimson)):
        print(f"  {label} avg={sum(p.overall for p in squad)/11:.1f}")
        for p in squad:
            print(f"    {p.position:3} ovr={p.overall:3} sho={p.sho:3} {p.name}")
    print(format_zone_breakdown(mirai, "Mirai"))
    print(format_zone_breakdown(crimson, "Crimson"))
    print(
        "Crimson attack-zone players:",
        [p.name for p in crimson if p.position.upper() in {"FWD", "ST", "CF", "LW", "RW"}],
    )

    state = MatchState(
        home_rating=sum(p.overall for p in mirai) / 11,
        away_rating=sum(p.overall for p in crimson) / 11,
    )
    state, events, _ = await collect_match_events_v3(
        state, mirai, crimson, "Mirai MidNight", "Crimson FC", SEED
    )
    goals = [e for e in events if e.get("type") == "GOAL"]
    print(f"\nREPLAY seed={SEED} -> {state.home_score}-{state.away_score}")
    for g in goals:
        print(f"  {g['minute']}' {g['actor']} ({g['team']})")
    print(
        "shots",
        state.live_stats.home_shots,
        "-",
        state.live_stats.away_shots,
        "poss%",
        state.live_stats.possession_home_pct(),
        "-",
        state.live_stats.possession_away_pct(),
        "momentum",
        state.momentum,
    )

    away_wins = blowouts = mirai_wins = draws = 0
    score_sums = [0, 0]
    for i in range(100):
        st = MatchState(
            home_rating=sum(p.overall for p in mirai) / 11,
            away_rating=sum(p.overall for p in crimson) / 11,
        )
        st, _, _ = await collect_match_events_v3(
            st, mirai, crimson, "Mirai MidNight", "Crimson FC", SEED + i * 9973
        )
        score_sums[0] += st.home_score
        score_sums[1] += st.away_score
        if st.away_score > st.home_score:
            away_wins += 1
        elif st.home_score > st.away_score:
            mirai_wins += 1
        else:
            draws += 1
        if st.away_score - st.home_score >= 4:
            blowouts += 1
    print(
        f"\n100 random seeds: Mirai W-D-L = {mirai_wins}-{draws}-{away_wins}; "
        f"away blowouts>=4gd = {blowouts}; "
        f"avg score {score_sums[0]/100:.1f}-{score_sums[1]/100:.1f}"
    )


asyncio.run(main())
