"""Inspect the 0-7 Mirai vs Crimson friendly."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
RID = "5d6149fa-4d8a-4141-b30d-abd7aadde6d7"

with psycopg.connect(dsn, row_factory=dict_row) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT squad_snapshot, sim_seed, engine_version, home_score, away_score, "
        "home_discord_id, away_discord_id FROM match_runs WHERE id=%s",
        (RID,),
    )
    r = cur.fetchone()
    snap = r["squad_snapshot"] or {}
    print("seed", r["sim_seed"], "engine", r["engine_version"])
    print("score", r["home_score"], "-", r["away_score"])
    print("ids", r["home_discord_id"], "vs", r["away_discord_id"])
    print("snap keys", sorted(snap.keys()) if isinstance(snap, dict) else type(snap))

    Path("scratch/_friendly_snap.json").write_text(
        json.dumps(snap, indent=2, default=str), encoding="utf-8"
    )

    for side in ("home", "away"):
        squad = snap.get(f"{side}_squad") or []
        print(
            f"=== {side} name={snap.get(f'{side}_name')} "
            f"rating={snap.get(f'{side}_rating')} n={len(squad)} ==="
        )
        for p in squad:
            if not isinstance(p, dict):
                print(" ", p)
                continue
            print(
                f"  {p.get('name')} ovr={p.get('overall') or p.get('ovr')} "
                f"pos={p.get('position') or p.get('role')} "
                f"pac={p.get('pace') or p.get('pac')} sho={p.get('shooting') or p.get('sho')}"
            )

    # Harry Bennett card
    cur.execute(
        """
        SELECT id, name, owner_id, overall, position, pace, shooting, passing,
               dribbling, defending, physical, potential, rarity, fatigue, morale
        FROM player_cards WHERE name ILIKE %s AND owner_id = %s
        """,
        ("%Harry Bennett%", 840864839240253440),
    )
    print("=== Harry Bennett on Crimson ===")
    for row in cur.fetchall():
        print(row)
