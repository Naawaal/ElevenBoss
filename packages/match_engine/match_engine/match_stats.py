# packages/match_engine/match_engine/match_stats.py
"""Live and post-match statistics derived from NSS simulation."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MatchLiveStats(BaseModel):
    """Counters updated during stream_match; used for press-conference stats."""

    home_shots: int = 0
    away_shots: int = 0
    home_chances: int = 0
    away_chances: int = 0
    home_possession_ticks: int = 0
    away_possession_ticks: int = 0
    player_goals: dict[str, int] = Field(default_factory=dict)
    player_assists: dict[str, int] = Field(default_factory=dict)

    def record_chance(self, is_home: bool) -> None:
        if is_home:
            self.home_chances += 1
        else:
            self.away_chances += 1

    def record_shot(self, is_home: bool) -> None:
        if is_home:
            self.home_shots += 1
        else:
            self.away_shots += 1

    def record_possession(self, is_home: bool) -> None:
        if is_home:
            self.home_possession_ticks += 1
        else:
            self.away_possession_ticks += 1

    def record_goal(self, scorer: str, assister: str | None = None) -> None:
        self.player_goals[scorer] = self.player_goals.get(scorer, 0) + 1
        if assister:
            self.player_assists[assister] = self.player_assists.get(assister, 0) + 1

    def possession_home_pct(self) -> int:
        total = self.home_possession_ticks + self.away_possession_ticks
        if total <= 0:
            ch = self.home_chances + self.away_chances
            if ch <= 0:
                return 50
            return max(0, min(100, round(self.home_chances / ch * 100)))
        return max(0, min(100, round(self.home_possession_ticks / total * 100)))

    def possession_away_pct(self) -> int:
        return 100 - self.possession_home_pct()

    def pick_motm(self, fallback: str = "Match MVP") -> str:
        best_name = fallback
        best_score = -1
        for name, goals in self.player_goals.items():
            score = goals * 3 + self.player_assists.get(name, 0) * 2
            if score > best_score:
                best_score = score
                best_name = name
        if best_score > 0:
            return best_name
        for name, assists in self.player_assists.items():
            if assists * 2 > best_score:
                best_score = assists * 2
                best_name = name
        return best_name


def stats_from_events(
    events: list[dict],
    home_name: str,
) -> MatchLiveStats:
    """Rebuild stats from a completed event list (recovery / tests)."""
    live = MatchLiveStats()
    for ev in events:
        etype = ev.get("type", "")
        team = ev.get("team", "")
        is_home = team == home_name
        if etype == "CHANCE":
            live.record_chance(is_home)
        elif etype in ("GOAL", "MISS"):
            live.record_shot(is_home)
            if etype == "GOAL":
                live.record_goal(ev.get("actor", ""), ev.get("assister"))
        elif etype == "SAVE":
            live.record_shot(not is_home)
    return live


_POSITION_ZONES: dict[str, str] = {
    "GK": "gk",
    "DEF": "defense", "CB": "defense", "LB": "defense", "RB": "defense",
    "LWB": "defense", "RWB": "defense",
    "MID": "midfield", "CM": "midfield", "CDM": "midfield",
    "CAM": "midfield", "LM": "midfield", "RM": "midfield",
    "FWD": "attack", "ST": "attack", "CF": "attack",
    "LW": "attack", "RW": "attack",
}


def zone_averages(squad: list) -> dict[str, float]:
    """GK/DEF/MID/ATT zone OVR averages for transparency displays."""
    buckets: dict[str, list[float]] = {
        "gk": [], "defense": [], "midfield": [], "attack": [],
    }
    for p in squad:
        pos = p.position if hasattr(p, "position") else p.get("position", "MID")
        ovr = float(p.overall if hasattr(p, "overall") else p.get("overall", 50))
        zone = _POSITION_ZONES.get(str(pos).upper(), "midfield")
        buckets[zone].append(ovr)

    fallback = sum(
        float(p.overall if hasattr(p, "overall") else p.get("overall", 50))
        for p in squad
    ) / max(1, len(squad))

    def _avg(vals: list[float], fb: float) -> float:
        return sum(vals) / len(vals) if vals else fb

    return {
        "gk": round(_avg(buckets["gk"], fallback * 0.9), 1),
        "defense": round(_avg(buckets["defense"], fallback), 1),
        "midfield": round(_avg(buckets["midfield"], fallback), 1),
        "attack": round(_avg(buckets["attack"], fallback), 1),
    }


def format_zone_breakdown(squad: list, label: str = "Squad") -> str:
    z = zone_averages(squad)
    return (
        f"**{label}** — GK {z['gk']} | DEF {z['defense']} | "
        f"MID {z['midfield']} | ATT {z['attack']}"
    )
