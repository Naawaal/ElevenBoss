# packages/match_engine/match_engine/v3/projectors.py
"""Event projectors — box score, replay timeline, post-match explainability."""
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


def _humanize_hint(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "moment"
    if "_" in text and " " not in text:
        return text.replace("_", " ")
    return text


def _tip_from_event(ev: MatchEventV3, *, text_key: str, default_hint: str) -> dict[str, Any]:
    hint = ev.causal_hint or default_hint
    if not ev.causal_hint:
        if ev.type == "GOAL":
            actor = ev.payload.get("actor")
            hint = f"Goal — {actor}" if actor else "Goal"
        elif ev.type == "TACTICAL_DECISION":
            tactic = ev.payload.get("tactic") or "tactical change"
            hint = f"Tactical switch — {tactic}"
        elif ev.type == "DECISION_WINDOW":
            hint = f"Decision window ({ev.minute}')"
        elif ev.type == "CHANCE":
            hint = "Clear chance"
        elif ev.type == "SAVE":
            hint = "Crucial save"
    return {
        "minute": ev.minute,
        "type": ev.type,
        "causal_hint": _humanize_hint(str(hint)),
        "seq": ev.seq,
        "text_key": text_key,
    }


def project_explanation(
    events: list[MatchEventV3],
    *,
    result: str = "draw",
) -> Explanation:
    """Deterministic turning points from goals, decisions, then chance/save fallbacks.

    Never invents events — only projects from the provided stream. Caps at 5 tips.
    """
    goals = [ev for ev in events if ev.type == "GOAL"]
    decisions = [
        ev
        for ev in events
        if ev.type in ("TACTICAL_DECISION", "DECISION_WINDOW")
    ]
    chances = [ev for ev in events if ev.type == "CHANCE"]
    saves = [ev for ev in events if ev.type == "SAVE"]

    selected: list[MatchEventV3] = []
    seen: set[int] = set()

    def _take(ev: MatchEventV3) -> None:
        if ev.seq in seen or len(selected) >= 5:
            return
        seen.add(ev.seq)
        selected.append(ev)

    for ev in goals:
        _take(ev)
    for ev in decisions:
        _take(ev)

    if not selected:
        if chances:
            _take(chances[len(chances) // 2])
        elif saves:
            _take(saves[-1])

    text_key_for = {
        "GOAL": "goal",
        "TACTICAL_DECISION": "tactical",
        "DECISION_WINDOW": "window",
        "CHANCE": "chance",
        "SAVE": "save",
    }
    default_hint_for = {
        "GOAL": "goal",
        "TACTICAL_DECISION": "tactical change",
        "DECISION_WINDOW": "decision window",
        "CHANCE": "chance_pattern",
        "SAVE": "crucial_save",
    }
    selected.sort(key=lambda e: e.seq)
    turning = [
        _tip_from_event(
            ev,
            text_key=text_key_for.get(ev.type, "moment"),
            default_hint=default_hint_for.get(ev.type, "moment"),
        )
        for ev in selected[:5]
    ]
    primary = turning[-1]["seq"] if turning else None
    if goals:
        primary = goals[-1].seq

    headline = {
        "win": "Victory forged in key moments",
        "loss": "Decided by critical passages of play",
        "draw": "Honours even after a contested match",
    }.get(result, "Match complete")
    return Explanation(
        headline=headline,
        turning_points=turning,
        primary_turning_seq=primary,
    )
