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

from player_engine import calculate_true_ovr, generate_potential

# Weights matching POSITION_WEIGHTS in player_engine
_WEIGHTS = {
    "FWD": {"pac": 0.20, "sho": 0.35, "pas": 0.10, "dri": 0.20, "def": 0.05, "phy": 0.10},
    "MID": {"pac": 0.10, "sho": 0.15, "pas": 0.25, "dri": 0.20, "def": 0.15, "phy": 0.15},
    "DEF": {"pac": 0.15, "sho": 0.05, "pas": 0.10, "dri": 0.05, "def": 0.40, "phy": 0.25},
    "GK": {"pac": 0.15, "sho": 0.00, "pas": 0.15, "dri": 0.00, "def": 0.50, "phy": 0.20}
}

def _make_player(position: str, rarity: str, names: dict[str, list[str]]) -> GachaPlayer:
    lo, hi = RARITY_RATING_RANGES[rarity]
    target = random.randint(lo, hi)
    
    first_name = random.choice(names["first"])
    last_name = random.choice(names["last"])

    # Generate age
    age_roll = random.random()
    if age_roll < 0.40:
        age = random.randint(16, 21)
    elif age_roll < 0.80:
        age = random.randint(22, 27)
    elif age_roll < 0.95:
        age = random.randint(28, 32)
    else:
        age = random.randint(33, 36)

    potential = generate_potential(target, age, rarity, position)

    # Roll 6 stats using position weights to create realistic distributions
    weights = _WEIGHTS.get(position, _WEIGHTS["MID"])
    stats = {}
    for attr, weight in weights.items():
        if weight >= 0.25:
            # Primary attributes get a boost
            stats[attr] = target + random.randint(2, 12)
        elif weight >= 0.15:
            # Secondary attributes are close to the target
            stats[attr] = target + random.randint(-5, 5)
        else:
            # Dump attributes are lower than the target
            stats[attr] = target + random.randint(-20, -5)
        # Clamp to reasonable limits (10 to 99)
        stats[attr] = max(10, min(99, stats[attr]))
        
    # Recalculate true OVR based on generated stats
    overall = calculate_true_ovr(position, stats, [], potential)
    
    # If the calculated overall falls outside of the range of the rarity, adjust stats slightly to match target
    diff = target - overall
    attempts = 0
    while diff != 0 and attempts < 10:
        shift = 1 if diff > 0 else -1
        for attr in stats:
            if weights[attr] > 0:
                stats[attr] = max(10, min(99, stats[attr] + shift))
        overall = calculate_true_ovr(position, stats, [], potential)
        diff = target - overall
        attempts += 1

    return GachaPlayer(
        name=f"{first_name} {last_name}",
        position=position,
        rarity=rarity,
        base_rating=overall,
        overall=overall,
        pac=stats["pac"],
        sho=stats["sho"],
        pas=stats["pas"],
        dri=stats["dri"],
        def_stat=stats["def"],
        phy=stats["phy"],
        potential=potential,
        age=age
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
