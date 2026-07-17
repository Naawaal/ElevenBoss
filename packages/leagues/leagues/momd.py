# packages/leagues/leagues/momd.py
"""Manager of the Matchday selection (manual human wins only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class MomdWinner:
    player_id: int
    fixture_id: str
    margin: int
    goals_for: int
    home_score: int
    away_score: int


def _club_ai(fixture: Mapping[str, Any], side: str) -> bool:
    nested = fixture.get(side)
    if isinstance(nested, Mapping):
        return bool(nested.get("is_ai"))
    key = f"{side}_is_ai"
    return bool(fixture.get(key))


def select_momd_winner(fixtures: Sequence[Mapping[str, Any]]) -> MomdWinner | None:
    """
    Pick MoMD among played fixtures.

    Eligible: resolved_by == 'manual', decisive win, winner is_ai == false.
    Rank: margin DESC, GF DESC, winner player_id ASC.
    """
    candidates: list[MomdWinner] = []
    for f in fixtures:
        if not f.get("is_played"):
            continue
        if f.get("resolved_by") != "manual":
            continue
        hs = f.get("home_score")
        aws = f.get("away_score")
        if hs is None or aws is None:
            continue
        home_score = int(hs)
        away_score = int(aws)
        if home_score == away_score:
            continue
        if home_score > away_score:
            winner_id = int(f["home_team_id"])
            if _club_ai(f, "home"):
                continue
            gf = home_score
            margin = home_score - away_score
        else:
            winner_id = int(f["away_team_id"])
            if _club_ai(f, "away"):
                continue
            gf = away_score
            margin = away_score - home_score
        fid = f.get("id")
        if fid is None:
            continue
        candidates.append(
            MomdWinner(
                player_id=winner_id,
                fixture_id=str(fid),
                margin=margin,
                goals_for=gf,
                home_score=home_score,
                away_score=away_score,
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda w: (-w.margin, -w.goals_for, w.player_id))
    return candidates[0]
