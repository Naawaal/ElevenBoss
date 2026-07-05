# packages/gacha/gacha/generator.py
from __future__ import annotations
import os
import json
import random
from .models import GachaPlayer, GachaPack, StarterSquad, RARITY_RATING_RANGES

# Positional blueprints
_POSITIONS = ["GK", "DEF", "MID", "FWD"]
_POSITION_WEIGHTS = [10, 30, 30, 30]

_YOUTH_POSITIONS: list[str] = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD"]
_MARQUEE_POSITIONS: list[str] = ["DEF", "DEF", "MID", "MID", "MID", "FWD"]

def _load_names() -> dict[str, list[str]]:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(dir_path, "data", "player_names.json")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _make_player(position: str, rarity: str, names: dict[str, list[str]]) -> GachaPlayer:
    lo, hi = RARITY_RATING_RANGES[rarity]
    rating = random.randint(lo, hi)
    first_name = random.choice(names["first"])
    last_name = random.choice(names["last"])
    return GachaPlayer(
        name=f"{first_name} {last_name}",
        position=position,
        rarity=rarity,
        base_rating=rating,
        overall=rating,
    )

def generate_pack(n: int = 5) -> GachaPack:
    """Generates a randomized pack of n players with weighted rarities."""
    names = _load_names()
    players = []
    rarity_choices = ["Common", "Rare", "Epic", "Legendary"]
    rarity_weights = [60, 30, 8, 2]

    for _ in range(n):
        rarity = random.choices(rarity_choices, weights=rarity_weights, k=1)[0]
        position = random.choices(_POSITIONS, weights=_POSITION_WEIGHTS, k=1)[0]
        players.append(_make_player(position, rarity, names))

    return GachaPack(players=players)

def generate_starter_squad() -> StarterSquad:
    """
    Generates a guaranteed 11-player squad for onboarding:
    - 1 Marquee: Rare (80%) or Epic (20%), non-GK position.
    - 10 Youth: All Common, covering the full 4-4-2 formation blueprint.
    Returns a StarterSquad where the youth list has the Marquee's positional slot
    replaced by the Marquee card itself (youth keep Common coverage for all other slots).
    """
    names = _load_names()

    # 1. Draw Marquee rarity and position
    marquee_rarity = random.choices(["Rare", "Epic"], weights=[80, 20], k=1)[0]
    marquee_position = random.choice(_MARQUEE_POSITIONS)
    marquee = _make_player(marquee_position, marquee_rarity, names)

    # 2. Build 10 Common youth players covering ALL 11 positional slots,
    #    then remove ONE card matching the Marquee's position so the total is 10.
    full_common_positions = list(_YOUTH_POSITIONS)  # 11 slots including GK
    full_common_positions.remove(marquee_position)  # Remove one slot of Marquee's type
    
    youth = [_make_player(pos, "Common", names) for pos in full_common_positions]

    return StarterSquad(marquee=marquee, youth=youth)
