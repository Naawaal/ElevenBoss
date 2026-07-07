#!/usr/bin/env python3
"""Simulate league season logic offline (US-26 smoke test)."""
from __future__ import annotations

from match_engine import generate_round_robin_fixtures
from match_engine.fixture_generator import expected_fixture_counts
from leagues import distribute_finish_prizes, format_standings_table, sort_standings


def _build_standings(club_ids: list[int], results: list[tuple]) -> list[dict]:
    rows = []
    for cid in club_ids:
        rows.append({
            "discord_id": cid,
            "club_name": f"Club {cid}",
            "is_ai": cid < 0,
            "is_active": True,
            "wins": 0, "draws": 0, "losses": 0,
            "goals_for": 0, "goals_against": 0,
            "matches_played": 0, "points": 0, "goal_difference": 0,
        })
    idx = {r["discord_id"]: r for r in rows}
    fixtures = []
    for md, home, away, hs, as_ in results:
        fixtures.append({
            "is_played": True, "matchday": md,
            "home_team_id": home, "away_team_id": away,
            "home_score": hs, "away_score": as_,
        })
        for pid, gf, ga, res in ((home, hs, as_, "home"), (away, as_, hs, "away")):
            r = idx[pid]
            r["matches_played"] += 1
            r["goals_for"] += gf
            r["goals_against"] += ga
            r["goal_difference"] = r["goals_for"] - r["goals_against"]
            if gf > ga:
                r["wins"] += 1
                r["points"] += 3
            elif gf == ga:
                r["draws"] += 1
                r["points"] += 1
            else:
                r["losses"] += 1
    return sort_standings(list(idx.values()), fixtures), fixtures


def main() -> None:
    club_ids = [1, 2, 3, 4, -1, -2, -3, -4]
    str_ids = [str(c) for c in club_ids]
    generated = generate_round_robin_fixtures(str_ids, double_round_robin=True)
    counts = expected_fixture_counts(8, double_round_robin=True)
    assert len(generated) == counts["total_fixtures"]

    # Simulate MD1 with random-ish results
    md1 = [f for f in generated if f.week == 1]
    results = []
    for i, f in enumerate(md1):
        hs, as_ = (2, 1) if i % 2 == 0 else (1, 1)
        results.append((1, int(f.home_club_id), int(f.away_club_id), hs, as_))

    standings, fixtures = _build_standings(club_ids, results)
    table = format_standings_table(standings, fixtures)
    prizes = distribute_finish_prizes(standings, 5000, 200)

    print("=== 8-club season smoke (MD1) ===")
    print(table)
    print(f"\nPrize rows: {len(prizes)}")
    print(f"Champion coins: {prizes[0].coins}")
    assert prizes[0].coins == 3000
    print("OK")


if __name__ == "__main__":
    main()
