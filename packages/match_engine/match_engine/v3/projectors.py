# packages/match_engine/match_engine/v3/projectors.py
"""Event projectors — box score, replay timeline stubs, explainability stub."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .events import MatchEventV3


class BoxScore(BaseModel):
    possession_home: int = 50
    possession_away: int = 50
    shots_home: int = 0
    shots_away: int = 0
    chances_home: int = 0
    chances_away: int = 0
    goals_home: int = 0
    goals_away: int = 0
    motm_name: str = "TBD"


class ReplayTimeline(BaseModel):
    """Stub for future Discord/website replay UI."""

    entries: list[dict[str, Any]] = Field(default_factory=list)


class Explanation(BaseModel):
    headline: str = ""
    turning_points: list[dict[str, Any]] = Field(default_factory=list)
    primary_turning_seq: int | None = None


def _side_of(ev: MatchEventV3, home_name: str) -> str | None:
    team = ev.payload.get("team")
    if ev.side in ("home", "away"):
        return ev.side
    if team == home_name:
        return "home"
    if team:
        return "away"
    return None


def project_box_score(
    events: list[MatchEventV3],
    *,
    home_name: str = "Home",
) -> BoxScore:
    poss_h = poss_a = 0
    shots_h = shots_a = 0
    chance_h = chance_a = 0
    goals_h = goals_a = 0
    contrib: dict[str, int] = {}

    for ev in events:
        side = _side_of(ev, home_name)
        if ev.type == "POSSESSION_START" or (
            ev.type in ("CHANCE",) and False
        ):
            pass
        # Possession ticks: CHANCE/FOUL midfield recorded as POSSESSION in payload
        if ev.type in ("CHANCE", "GOAL", "MISS", "SAVE"):
            if side == "home":
                chance_h += 1 if ev.type == "CHANCE" else 0
                if ev.type in ("GOAL", "MISS", "SAVE"):
                    shots_h += 1
                if ev.type == "GOAL":
                    goals_h += 1
                    actor = str(ev.payload.get("actor") or "")
                    contrib[actor] = contrib.get(actor, 0) + 3
                    assister = ev.payload.get("assister")
                    if assister:
                        contrib[str(assister)] = contrib.get(str(assister), 0) + 2
            elif side == "away":
                chance_a += 1 if ev.type == "CHANCE" else 0
                if ev.type in ("GOAL", "MISS", "SAVE"):
                    shots_a += 1
                if ev.type == "GOAL":
                    goals_a += 1
                    actor = str(ev.payload.get("actor") or "")
                    contrib[actor] = contrib.get(actor, 0) + 3
                    assister = ev.payload.get("assister")
                    if assister:
                        contrib[str(assister)] = contrib.get(str(assister), 0) + 2
        # Approximate possession from chance creation share
        if ev.type == "CHANCE":
            if side == "home":
                poss_h += 1
            elif side == "away":
                poss_a += 1

    total = max(1, poss_h + poss_a)
    ph = int(round(100 * poss_h / total)) if (poss_h + poss_a) else 50
    pa = 100 - ph
    motm = "TBD"
    if contrib:
        motm = sorted(contrib.items(), key=lambda x: (-x[1], x[0]))[0][0]

    # Prefer score_update on FULL_TIME if present
    for ev in reversed(events):
        if ev.type == "FULL_TIME":
            su = str(ev.payload.get("score_update") or "")
            if " - " in su:
                try:
                    a, b = su.split(" - ", 1)
                    goals_h, goals_a = int(a.strip()), int(b.strip())
                except ValueError:
                    pass
            break

    return BoxScore(
        possession_home=ph,
        possession_away=pa,
        shots_home=shots_h,
        shots_away=shots_a,
        chances_home=chance_h,
        chances_away=chance_a,
        goals_home=goals_h,
        goals_away=goals_a,
        motm_name=motm,
    )


def project_replay_timeline(events: list[MatchEventV3]) -> ReplayTimeline:
    entries = [
        {
            "seq": ev.seq,
            "minute": ev.minute,
            "type": ev.type,
            "category": ev.category.value,
        }
        for ev in events
        if ev.category.value != "projection"
    ]
    return ReplayTimeline(entries=entries)


def project_explanation(
    events: list[MatchEventV3],
    *,
    result: str = "draw",
) -> Explanation:
    """Phase 0 stub — deterministic turning points from GOAL events."""
    goals = [ev for ev in events if ev.type == "GOAL"]
    turning = [
        {
            "minute": ev.minute,
            "type": ev.type,
            "causal_hint": ev.causal_hint or "goal",
            "seq": ev.seq,
            "text_key": "goal",
        }
        for ev in goals
    ]
    primary = turning[-1]["seq"] if turning else None
    if not turning:
        chances = [ev for ev in events if ev.type == "CHANCE"]
        if chances:
            ev = chances[len(chances) // 2]
            turning = [{
                "minute": ev.minute,
                "type": ev.type,
                "causal_hint": "chance_pattern",
                "seq": ev.seq,
                "text_key": "chance",
            }]
            primary = ev.seq
    headline = {
        "win": "Victory forged in key moments",
        "loss": "Decided by critical passages of play",
        "draw": "Honours even after a contested match",
    }.get(result, "Match complete")
    return Explanation(
        headline=headline,
        turning_points=turning[:5],
        primary_turning_seq=primary,
    )
