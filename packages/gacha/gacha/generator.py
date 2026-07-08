# packages/gacha/gacha/generator.py
from __future__ import annotations
import os
import json
import random
from .models import GachaPlayer, GachaPack, StarterSquad, RARITY_RATING_RANGES

_POSITIONS = ["GK", "DEF", "MID", "FWD"]
_POSITION_WEIGHTS = [10, 30, 30, 30]

_YOUTH_POSITIONS: list[str] = ["GK", "DEF", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD"]
_MARQUEE_POSITIONS: list[str] = ["DEF", "DEF", "MID", "MID", "MID", "FWD"]

def _load_names() -> dict[str, list[str]]:
    dir_path = os.path.dirname(os.path.realpath(__file__))
    json_path = os.path.join(dir_path, "data", "player_names.json")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

from player_engine import create_player_card, generate_youth_intake_cards


def _make_player(position: str, rarity: str, names: dict[str, list[str]]) -> GachaPlayer:
    lo, hi = RARITY_RATING_RANGES[rarity]
    target = random.randint(lo, hi)
    first_name = random.choice(names["first"])
    last_name = random.choice(names["last"])
    data = create_player_card(
        position=position,
        rarity=rarity,
        target_ovr=target,
        first_name=first_name,
        last_name=last_name,
    )
    return GachaPlayer(
        name=data["name"],
        position=data["position"],
        rarity=data["rarity"],
        base_rating=data["base_rating"],
        overall=data["overall"],
        pac=data["pac"],
        sho=data["sho"],
        pas=data["pas"],
        dri=data["dri"],
        def_stat=data["def"],
        phy=data["phy"],
        potential=data["potential"],
        age=data["age"],
        date_of_birth=data["date_of_birth"],
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
    """
    names = _load_names()

    marquee_rarity = random.choices(["Rare", "Epic"], weights=[80, 20], k=1)[0]
    marquee_position = random.choice(_MARQUEE_POSITIONS)
    marquee = _make_player(marquee_position, marquee_rarity, names)

    full_common_positions = list(_YOUTH_POSITIONS)
    full_common_positions.remove(marquee_position)

    youth = [_make_player(pos, "Common", names) for pos in full_common_positions]

    return StarterSquad(marquee=marquee, youth=youth)


def generate_youth_intake(count: int | None = None, *, academy_level: int = 1) -> list[GachaPlayer]:
    """Seasonal academy intake — quality scales with Youth Academy level (Phase C)."""
    names = _load_names()
    rows = generate_youth_intake_cards(
        count,
        academy_level=academy_level,
        first_names=names["first"],
        last_names=names["last"],
    )
    return [
        GachaPlayer(
            name=row["name"],
            position=row["position"],
            rarity=row["rarity"],
            base_rating=row["base_rating"],
            overall=row["overall"],
            pac=row["pac"],
            sho=row["sho"],
            pas=row["pas"],
            dri=row["dri"],
            def_stat=row["def"],
            phy=row["phy"],
            potential=row["potential"],
            age=row["age"],
            date_of_birth=row["date_of_birth"],
        )
        for row in rows
    ]
