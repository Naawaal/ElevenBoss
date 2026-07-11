# packages/match_engine/match_engine/phase_stats.py
"""Phase-specific stat resolution and playstyle bonuses for NSS."""
from __future__ import annotations

from enum import Enum

# +2% success per matching playstyle in the relevant phase (spec AC-08b)
PLAYSTYLE_STAT_MAP: dict[str, str] = {
    "Rapid": "pac",
    "Quick Step": "pac",
    "speed_boost": "pac",
    "Speedster": "pac",
    "Finesse Shot": "sho",
    "Power Header": "sho",
    "shooting_boost": "sho",
    "Whipped Pass": "pas",
    "Tiki Taka": "pas",
    "passing_boost": "pas",
    "Playmaker": "pas",
    "Technical": "dri",
    "Trickster": "dri",
    "dribble_boost": "dri",
    "Intercept": "def_stat",
    "Slide Tackle": "def_stat",
    "defense_boost": "def_stat",
    "Bruiser": "phy",
    "Relentless": "phy",
    "physical_boost": "phy",
}

PLAYSTYLE_BONUS = 0.02


class PhaseStat(str, Enum):
    MIDFIELD = "midfield"
    PASSING = "pas"
    ATTACK = "attack"
    SHOOTING = "sho"
    PACE = "pac"
    DEFENSE = "defense"
    GOALKEEPING = "gk"


_POSITION_ZONES: dict[str, str] = {
    "GK": "gk",
    "DEF": "defense", "CB": "defense", "LB": "defense", "RB": "defense",
    "LWB": "defense", "RWB": "defense",
    "MID": "midfield", "CM": "midfield", "CDM": "midfield",
    "CAM": "midfield", "LM": "midfield", "RM": "midfield",
    "FWD": "attack", "ST": "attack", "CF": "attack",
    "LW": "attack", "RW": "attack",
}

_ZONE_FOR_PHASE: dict[PhaseStat, str] = {
    PhaseStat.MIDFIELD: "midfield",
    PhaseStat.PASSING: "midfield",
    PhaseStat.ATTACK: "attack",
    PhaseStat.SHOOTING: "attack",
    PhaseStat.PACE: "attack",
    PhaseStat.DEFENSE: "defense",
    PhaseStat.GOALKEEPING: "gk",
}

_STAT_ATTR: dict[PhaseStat, str] = {
    PhaseStat.MIDFIELD: "overall",
    PhaseStat.PASSING: "pas",
    PhaseStat.ATTACK: "dri",
    PhaseStat.SHOOTING: "sho",
    PhaseStat.PACE: "pac",
    PhaseStat.DEFENSE: "def_stat",
    PhaseStat.GOALKEEPING: "def_stat",
}


def _get_attr(player, attr: str) -> float:
    if attr == "overall":
        return float(player.overall if hasattr(player, "overall") else player.get("overall", 50))
    if attr == "def_stat":
        if hasattr(player, "def_stat"):
            return float(player.def_stat)
        return float(player.get("def", player.get("def_stat", 50)))
    return float(getattr(player, attr, None) or player.get(attr, 50))


def _zone_players(squad: list, zone: str) -> list:
    out = []
    for p in squad:
        pos = p.position if hasattr(p, "position") else p.get("position", "MID")
        if _POSITION_ZONES.get(str(pos).upper(), "midfield") == zone:
            out.append(p)
    return out


def playstyle_bonus(squad: list, zone: str, stat_key: str) -> float:
    players = _zone_players(squad, zone) or squad
    bonus = 0.0
    for p in players:
        styles = p.playstyles if hasattr(p, "playstyles") else p.get("playstyles", [])
        for ps in styles or []:
            if PLAYSTYLE_STAT_MAP.get(ps) == stat_key:
                bonus += PLAYSTYLE_BONUS
    return min(bonus, 0.06)  # cap +6% from playstyles


def phase_stat_value(
    squad: list,
    phase: PhaseStat,
    zone_fallback: float,
) -> float:
    """Blend zone OVR (70%) with fatigue-adjusted phase attribute average (30%)."""
    from player_engine import fatigue_stat_multiplier
    from .substitution_resolve import COMPROMISED_PHASE_MULT, EMERGENCY_GK_DEF_MULT

    zone = _ZONE_FOR_PHASE[phase]
    attr = _STAT_ATTR[phase]
    players = _zone_players(squad, zone)
    if not players:
        return zone_fallback
    ovrs = [_get_attr(p, "overall") for p in players]
    specifics = []
    for p in players:
        raw = _get_attr(p, attr)
        fatigue = int(getattr(p, "fatigue", None) or (p.get("fatigue", 100) if isinstance(p, dict) else 100))
        val = raw * fatigue_stat_multiplier(fatigue, attr)
        compromised = bool(
            getattr(p, "compromised", False)
            or (p.get("compromised") if isinstance(p, dict) else False)
        )
        if compromised:
            val *= COMPROMISED_PHASE_MULT
        emergency = bool(
            getattr(p, "emergency_gk", False)
            or (p.get("emergency_gk") if isinstance(p, dict) else False)
        )
        if emergency and phase == PhaseStat.GOALKEEPING:
            val *= EMERGENCY_GK_DEF_MULT
        specifics.append(val)
    blended = 0.7 * (sum(ovrs) / len(ovrs)) + 0.3 * (sum(specifics) / len(specifics))
    stat_key = attr if attr != "overall" else "overall"
    return blended + playstyle_bonus(squad, zone, stat_key) * 100.0
