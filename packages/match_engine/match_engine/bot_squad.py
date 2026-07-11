# packages/match_engine/match_engine/bot_squad.py
"""Ephemeral named XIs for bot/AI opponents (live match immersion)."""
from __future__ import annotations

import json
import random
from pathlib import Path

from .models import MatchPlayerCard

# 4-4-2 blueprint — full zone coverage for phase_stat_value
_POSITIONS_442: list[str] = [
    "GK",
    "DEF", "DEF", "DEF", "DEF",
    "MID", "MID", "MID", "MID",
    "FWD", "FWD",
]

_FALLBACK_FIRST = ["Alex", "Sam", "Jordan", "Casey", "Riley", "Morgan", "Quinn", "Avery"]
_FALLBACK_LAST = ["Hayes", "Brooks", "Reed", "Cole", "Bennett", "Foster", "Hayes", "Stone"]


def _load_names() -> dict[str, list[str]]:
    # packages/gacha/gacha/data/player_names.json relative to packages/
    path = Path(__file__).resolve().parents[2] / "gacha" / "gacha" / "data" / "player_names.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("first") and data.get("last"):
            return data
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {"first": list(_FALLBACK_FIRST), "last": list(_FALLBACK_LAST)}


def _unique_name(rng: random.Random, names: dict[str, list[str]], used: set[str]) -> str:
    firsts = names["first"]
    lasts = names["last"]
    for _ in range(64):
        name = f"{rng.choice(firsts)} {rng.choice(lasts)}"
        if name not in used:
            used.add(name)
            return name
    # ponytail: collision after 64 tries — suffix is fine for ephemeral bot XI
    name = f"{rng.choice(firsts)} {rng.choice(lasts)} {rng.randint(1, 99)}"
    used.add(name)
    return name


def _near_ovr(rng: random.Random, ovr: int) -> int:
    return max(1, min(99, ovr + rng.randint(-3, 3)))


def build_bot_match_squad(target_ovr: int, rng: random.Random) -> list[MatchPlayerCard]:
    """Build an 11-player named bot XI centered on target_ovr."""
    names = _load_names()
    used: set[str] = set()
    target = max(1, min(99, int(target_ovr)))
    cards: list[MatchPlayerCard] = []
    for pos in _POSITIONS_442:
        ovr = max(1, min(99, target + rng.randint(-2, 2)))
        cards.append(
            MatchPlayerCard(
                name=_unique_name(rng, names, used),
                position=pos,
                overall=ovr,
                pac=_near_ovr(rng, ovr),
                sho=_near_ovr(rng, ovr),
                pas=_near_ovr(rng, ovr),
                dri=_near_ovr(rng, ovr),
                def_stat=_near_ovr(rng, ovr),
                phy=_near_ovr(rng, ovr),
            )
        )
    return cards
